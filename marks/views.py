from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.contrib import messages

from accounts.models import UserProfile
from core.models import Notification
from .models import Subject, StudentMark, SEMESTER_CHOICES


def _get_role(user):
    p = UserProfile.objects.filter(user=user).first()
    return (p.role or "").strip().lower() if p else ""

def _get_dept(user):
    p = UserProfile.objects.filter(user=user).first()
    return (p.department or "").strip() if p else ""


# ── Subject Management ─────────────────────────────────
@login_required
def subject_list(request):
    role = _get_role(request.user)
    dept = _get_dept(request.user)

    if role == "student":
        return redirect("marks_analytics")

    if role not in ("staff", "proctor", "hod", "dean", "principal"):
        return HttpResponseForbidden("Not allowed")

    if role in ("staff", "proctor"):
        subjects = Subject.objects.filter(
            department=dept, staff=request.user
        ).order_by("semester", "name")
    elif role == "hod":
        subjects = Subject.objects.filter(
            department=dept
        ).order_by("semester", "name")
    else:
        subjects = Subject.objects.all().order_by("department", "semester", "name")

    return render(request, "marks/subject_list.html", {
        "subjects":         subjects,
        "role":             role,
        "dept":             dept,
        "semester_choices": SEMESTER_CHOICES,
    })


@login_required
def add_subject(request):
    role = _get_role(request.user)
    dept = _get_dept(request.user)

    if role not in ("staff", "proctor"):
        return HttpResponseForbidden("Not allowed")

    if request.method == "POST":
        name     = request.POST.get("name", "").strip()
        code     = request.POST.get("code", "").strip()
        semester = request.POST.get("semester", "").strip()
        is_lab   = request.POST.get("is_lab") == "on"

        if not name or not semester:
            messages.error(request, "Subject name and semester are required.")
            return redirect("subject_list")

        Subject.objects.get_or_create(
            name=name, department=dept, semester=semester,
            defaults={"code": code, "is_lab": is_lab, "staff": request.user}
        )
        messages.success(request, f"Subject '{name}' added.")
        return redirect("subject_list")

    return redirect("subject_list")


@login_required
def delete_subject(request, pk):
    role = _get_role(request.user)
    if role not in ("staff", "proctor"):
        return HttpResponseForbidden("Not allowed")

    subject = get_object_or_404(Subject, pk=pk)
    subject.delete()
    messages.success(request, "Subject deleted.")
    return redirect("subject_list")


# ── Mark Entry ─────────────────────────────────────────
@login_required
def enter_marks(request, subject_id):
    role = _get_role(request.user)
    dept = _get_dept(request.user)

    if role not in ("staff", "proctor"):
        return HttpResponseForbidden("Only staff can enter marks")

    subject = get_object_or_404(Subject, id=subject_id, department=dept, staff=request.user)

    students = User.objects.filter(
        userprofile__role="student",
        userprofile__department=dept,
        userprofile__semester=subject.semester
    ).order_by("username")
    semester_filter = subject.semester

    exam_type = request.GET.get("exam", "mid1")
    existing  = StudentMark.objects.filter(
        subject=subject, exam_type=exam_type
    ).select_related("student")
    existing_map = {m.student_id: m for m in existing}

    if request.method == "POST":
        exam_type = request.POST.get("exam_type", "mid1")
        existing  = StudentMark.objects.filter(
            subject=subject, exam_type=exam_type
        ).select_related("student")
        existing_map = {m.student_id: m for m in existing}

        for student in students:
            sid = str(student.id)

            if exam_type == "lab":
                lab_int = request.POST.get(f"lab_internal_{sid}", "").strip()
                lab_ext = request.POST.get(f"lab_external_{sid}", "").strip()
                if lab_int != "" or lab_ext != "":
                    try:
                        StudentMark.objects.update_or_create(
                            student=student, subject=subject, exam_type="lab",
                            defaults={
                                "lab_internal": float(lab_int) if lab_int != "" else None,
                                "lab_external": float(lab_ext) if lab_ext != "" else None,
                                "entered_by":   request.user,
                            }
                        )
                    except Exception as e:
                        print(f"ERROR saving lab: {e}")
            else:
                obj  = request.POST.get(f"objective_{sid}",   "").strip()
                desc = request.POST.get(f"descriptive_{sid}", "").strip()
                asgn = request.POST.get(f"assignment_{sid}",  "").strip()
                if obj != "" or desc != "" or asgn != "":
                    try:
                        StudentMark.objects.update_or_create(
                            student=student, subject=subject, exam_type=exam_type,
                            defaults={
                                "objective":   float(obj)  if obj  != "" else None,
                                "descriptive": float(desc) if desc != "" else None,
                                "assignment":  float(asgn) if asgn != "" else None,
                                "entered_by":  request.user,
                            }
                        )
                    except Exception as e:
                        print(f"ERROR saving theory: {e}")

        # ✅ NEW: Notify all students marks posted
        notify_marks_posted(students, subject, exam_type)

        # ✅ Existing: Risk alerts
        _check_and_notify_at_risk(students, subject)
        return redirect(f"/marks/enter/{subject_id}/?exam={exam_type}&saved=1")

    return render(request, "marks/enter_marks.html", {
        "subject":          subject,
        "students":         students,
        "exam_type":        exam_type,
        "existing_map":     existing_map,
        "semester_filter":  semester_filter,
        "semester_choices": [(str(i), f"Semester {i}") for i in range(1, 9)],
    })


def _check_and_notify_at_risk(students, subject):
    from django.core.mail import send_mail
    from django.conf import settings

    for student in students:
        marks        = list(StudentMark.objects.filter(student=student, subject=subject))
        if not marks:
            continue

        theory_marks = [m for m in marks if m.exam_type in ("mid1", "mid2")]
        lab_marks    = [m for m in marks if m.exam_type == "lab"]
        at_risk      = False
        risk_detail  = ""

        if theory_marks:
            theory_avg = round(sum(m.theory_total() for m in theory_marks) / len(theory_marks), 1)
            if theory_avg < 12:
                at_risk     = True
                risk_detail = (
                    f"Your average internal marks in {subject.name} is {theory_avg}/30. "
                    f"Minimum required is 12."
                )

        if lab_marks:
            lab_mark = lab_marks[0]
            if (lab_mark.lab_internal or 0) < 12 or (lab_mark.lab_external or 0) < 28:
                at_risk     = True
                risk_detail = (
                    f"Your lab marks in {subject.name} — "
                    f"Internal: {lab_mark.lab_internal or 0}/30, "
                    f"External: {lab_mark.lab_external or 0}/70. "
                    f"Minimum: Internal 12, External 28."
                )

        if not at_risk:
            continue

        student_name = student.get_full_name() or student.username

        # Notify student
        Notification.objects.update_or_create(
            user=student,
            title=f"⚠️ At Risk — {subject.name}",
            defaults={
                "message": risk_detail,
                "link":    "/marks/my/",
                "is_read": False,
            }
        )

        # Email student
        if student.email:
            try:
                send_mail(
                    subject=f"⚠️ At Risk Alert — {subject.name} | CampusIQ",
                    message=(
                        f"Hello {student_name},\n\n"
                        f"This is an early warning alert from CampusIQ.\n\n"
                        f"Subject    : {subject.name}\n"
                        f"Department : {subject.department}\n"
                        f"Semester   : {subject.semester}\n\n"
                        f"⚠️ Warning : {risk_detail}\n\n"
                        f"Please improve your performance before semester exams.\n\n"
                        f"Login to CampusIQ to view your marks:\n"
                        f"http://192.168.37.1:8000/marks/my/\n\n"
                        f"Regards,\nCampusIQ Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[student.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Email error (student): {e}")

        # Notify proctor
        try:
            student_profile = UserProfile.objects.get(user=student)
            proctor = User.objects.filter(
                userprofile__role="proctor",
                userprofile__department=student_profile.department
            ).first()

            if proctor:
                Notification.objects.update_or_create(
                    user=proctor,
                    title=f"⚠️ At Risk — {student_name} in {subject.name}",
                    defaults={
                        "message": (
                            f"Student {student_name} is at risk in {subject.name}. "
                            f"{risk_detail}"
                        ),
                        "link":    "/marks/analytics/",
                        "is_read": False,
                    }
                )

                # Email proctor
                if proctor.email:
                    try:
                        send_mail(
                            subject=f"⚠️ Student At Risk — {student_name} | CampusIQ",
                            message=(
                                f"Hello {proctor.get_full_name() or proctor.username},\n\n"
                                f"Student {student_name} is at risk in {subject.name}.\n\n"
                                f"Subject    : {subject.name}\n"
                                f"Department : {subject.department}\n"
                                f"Semester   : {subject.semester}\n\n"
                                f"⚠️ Details : {risk_detail}\n\n"
                                f"Please counsel the student.\n\n"
                                f"View analytics:\n"
                                f"http://192.168.37.1:8000/marks/analytics/\n\n"
                                f"Regards,\nCampusIQ Team"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[proctor.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Email error (proctor): {e}")

        except Exception as e:
            print(f"Error notifying proctor: {e}")


# ── Student My Marks ────────────────────────────────────
@login_required
def student_marks(request):
    user    = request.user
    dept    = _get_dept(user)
    profile = UserProfile.objects.filter(user=user).first()

    student_semester = (profile.semester or "").strip() if profile else ""
    semester_filter  = request.GET.get("semester", student_semester)

    subjects = Subject.objects.filter(department=dept)
    if semester_filter:
        subjects = subjects.filter(semester=semester_filter)

    marks_data    = []
    overall_total = 0
    overall_max   = 0

    for subject in subjects:
        subject_marks = list(StudentMark.objects.filter(student=user, subject=subject))
        mid1 = next((m for m in subject_marks if m.exam_type == "mid1"), None)
        mid2 = next((m for m in subject_marks if m.exam_type == "mid2"), None)
        lab  = next((m for m in subject_marks if m.exam_type == "lab"),  None)

        theory_total = sum(m.theory_total() for m in [mid1, mid2] if m)
        theory_max   = sum(30 for m in [mid1, mid2] if m)
        lab_total    = ((lab.lab_internal or 0) + (lab.lab_external or 0)) if lab else 0
        lab_max      = 100 if lab else 0

        subject_total  = theory_total + lab_total
        subject_max    = theory_max + lab_max
        overall_total += subject_total
        overall_max   += subject_max

        at_risk = False
        if mid1 or mid2:
            theory_exams = [m for m in [mid1, mid2] if m]
            if sum(m.theory_total() for m in theory_exams) / len(theory_exams) < 12:
                at_risk = True
        if lab and ((lab.lab_internal or 0) < 12 or (lab.lab_external or 0) < 28):
            at_risk = True

        marks_data.append({
            "subject":       subject,
            "mid1":          mid1,
            "mid2":          mid2,
            "lab":           lab,
            "theory_total":  round(theory_total, 1),
            "theory_max":    theory_max,
            "lab_total":     round(lab_total, 1),
            "lab_max":       lab_max,
            "subject_total": round(subject_total, 1),
            "subject_max":   subject_max,
            "percentage":    round((subject_total / subject_max * 100), 1) if subject_max else 0,
            "at_risk":       at_risk,
        })

    # Position in semester & department
    semester_students = User.objects.filter(
        userprofile__role="student",
        userprofile__department=dept,
        userprofile__semester=semester_filter
    )
    student_scores = []
    for s in semester_students:
        s_subjects = Subject.objects.filter(department=dept, semester=semester_filter)
        s_total = 0
        for subj in s_subjects:
            for m in StudentMark.objects.filter(student=s, subject=subj):
                if m.exam_type in ("mid1", "mid2"):
                    s_total += m.theory_total()
                elif m.exam_type == "lab":
                    s_total += (m.lab_internal or 0) + (m.lab_external or 0)
        student_scores.append((s.id, round(s_total, 1)))

    student_scores.sort(key=lambda x: x[1], reverse=True)
    position       = next((i + 1 for i, (sid, _) in enumerate(student_scores) if sid == user.id), None)
    total_students = len(student_scores)
    my_score       = next((score for sid, score in student_scores if sid == user.id), 0)

    top3 = []
    for rank, (sid, score) in enumerate(student_scores[:3], start=1):
        try:
            top3.append({
                "rank":    rank,
                "student": User.objects.get(id=sid),
                "score":   score,
            })
        except User.DoesNotExist:
            pass

    return render(request, "marks/student_marks.html", {
        "marks_data":       marks_data,
        "semester_choices": [(str(i), f"Semester {i}") for i in range(1, 9)],
        "semester_filter":  semester_filter,
        "overall_total":    round(overall_total, 1),
        "overall_max":      overall_max,
        "overall_pct":      round((overall_total / overall_max * 100), 1) if overall_max else 0,
        "position":         position,
        "total_students":   total_students,
        "my_score":         my_score,
        "top3":             top3,
        "dept":             dept,
        "student_semester": semester_filter,
    })


# ── Analytics ──────────────────────────────────────────
@login_required
def marks_analytics(request):
    role = _get_role(request.user)
    dept = _get_dept(request.user)

    if role == "student":
        profile = UserProfile.objects.filter(user=request.user).first()
        student_semester = (profile.semester or "").strip() if profile else ""
        dept_filter      = dept
        semester_filter  = student_semester
    elif role in ("staff", "proctor", "hod"):
        dept_filter     = dept
        semester_filter = request.GET.get("semester", "")
    else:
        dept_filter     = request.GET.get("dept", "")
        semester_filter = request.GET.get("semester", "")

    subjects = Subject.objects.all()
    if dept_filter:     subjects = subjects.filter(department=dept_filter)
    if semester_filter: subjects = subjects.filter(semester=semester_filter)

    analytics = []
    for subject in subjects:
        marks          = list(StudentMark.objects.filter(subject=subject))
        total_students = User.objects.filter(
            userprofile__role="student",
            userprofile__department=subject.department
        ).count()
        appeared       = len(set(m.student_id for m in marks))
        student_theory = {}
        student_lab    = {}

        for m in marks:
            sid = m.student_id
            if m.exam_type in ("mid1", "mid2"):
                if sid not in student_theory:
                    student_theory[sid] = {"total": m.theory_total(), "count": 1}
                else:
                    student_theory[sid]["total"] += m.theory_total()
                    student_theory[sid]["count"] += 1
            elif m.exam_type == "lab":
                student_lab[sid] = m.passed()

        student_pass = {}
        all_sids = set(list(student_theory.keys()) + list(student_lab.keys()))
        for sid in all_sids:
            tp = student_theory[sid]["total"] / student_theory[sid]["count"] >= 12 if sid in student_theory else False
            lp = student_lab[sid] if sid in student_lab else False
            if sid in student_theory and sid in student_lab: student_pass[sid] = tp and lp
            elif sid in student_theory:                      student_pass[sid] = tp
            else:                                            student_pass[sid] = lp

        passed    = sum(1 for v in student_pass.values() if v)
        failed    = appeared - passed
        pass_rate = round((passed / appeared * 100)) if appeared > 0 else 0

        lab_fail_count    = sum(1 for sid, v in student_lab.items() if not v)
        theory_fail_count = sum(
            1 for sid in student_theory
            if student_theory[sid]["total"] / student_theory[sid]["count"] < 12
        )

        student_totals = {}
        for m in marks:
            sid   = m.student_id
            score = m.lab_total() if m.exam_type == "lab" else m.theory_total()
            if sid not in student_totals:
                student_totals[sid] = {"student": m.student, "total": score}
            else:
                student_totals[sid]["total"] += score

        topper_list = [(d["student"], round(d["total"], 1)) for d in student_totals.values()]
        topper_list.sort(key=lambda x: x[1], reverse=True)
        avg = round(sum(d["total"] for d in student_totals.values()) / len(student_totals), 1) if student_totals else 0

        analytics.append({
            "subject":           subject,
            "total_students":    total_students,
            "appeared":          appeared,
            "passed":            passed,
            "failed":            failed,
            "pass_rate":         pass_rate,
            "avg":               avg,
            "toppers":           topper_list[:3],
            "lab_fail_count":    lab_fail_count,
            "theory_fail_count": theory_fail_count,
            "has_lab":           len(student_lab) > 0,
            "has_theory":        len(student_theory) > 0,
        })

    # HOD Summary
    dept_summary = None
    if role == "hod" and analytics:
        total_subj  = len(analytics)
        all_toppers = []
        for a in analytics:
            all_toppers.extend(a["toppers"])
        all_toppers.sort(key=lambda x: x[1], reverse=True)
        dept_summary = {
            "total_subjects":  total_subj,
            "overall_pass":    round(sum(a["pass_rate"] for a in analytics) / total_subj) if total_subj else 0,
            "total_appeared":  sum(a["appeared"] for a in analytics),
            "total_passed":    sum(a["passed"]   for a in analytics),
            "total_failed":    sum(a["failed"]   for a in analytics),
            "worst_subject":   min(analytics, key=lambda x: x["pass_rate"]) if analytics else None,
            "best_subject":    max(analytics, key=lambda x: x["pass_rate"]) if analytics else None,
            "dept_toppers":    all_toppers[:3],
        }

    # Dean/Principal
    dept_comparison = []
    dept_wise       = []
    if role in ("dean", "principal"):
        all_depts_list = ['CSE', 'ECE', 'AIML', 'IT', 'CIVIL', 'MECH', 'EEE']

        for d in all_depts_list:
            d_subjs = Subject.objects.filter(department=d)
            if semester_filter:
                d_subjs = d_subjs.filter(semester=semester_filter)
            d_marks  = list(StudentMark.objects.filter(subject__in=d_subjs))
            if not d_marks:
                continue
            d_passed = sum(1 for m in d_marks if m.passed())
            d_total  = len(d_marks)
            dept_comparison.append({
                "dept":     d,
                "rate":     round((d_passed / d_total * 100)) if d_total else 0,
                "total":    d_total,
                "passed":   d_passed,
                "students": User.objects.filter(
                    userprofile__role="student",
                    userprofile__department=d
                ).count(),
            })

        depts_to_show = [dept_filter] if dept_filter else all_depts_list
        for d in depts_to_show:
            d_subjs = Subject.objects.filter(department=d)
            if semester_filter:
                d_subjs = d_subjs.filter(semester=semester_filter)

            d_analytics      = []
            d_all_toppers    = []
            d_total_passed   = 0
            d_total_appeared = 0

            for subject in d_subjs:
                marks = list(StudentMark.objects.filter(subject=subject))
                if not marks:
                    continue
                appeared = len(set(m.student_id for m in marks))
                st = {}; sl = {}
                for m in marks:
                    sid = m.student_id
                    if m.exam_type in ("mid1", "mid2"):
                        if sid not in st: st[sid] = {"total": m.theory_total(), "count": 1}
                        else: st[sid]["total"] += m.theory_total(); st[sid]["count"] += 1
                    elif m.exam_type == "lab":
                        sl[sid] = m.passed()
                sp = {}
                for sid in set(list(st.keys()) + list(sl.keys())):
                    tp = st[sid]["total"] / st[sid]["count"] >= 12 if sid in st else False
                    lp = sl[sid] if sid in sl else False
                    if sid in st and sid in sl: sp[sid] = tp and lp
                    elif sid in st:             sp[sid] = tp
                    else:                       sp[sid] = lp

                passed    = sum(1 for v in sp.values() if v)
                failed    = appeared - passed
                pass_rate = round((passed / appeared * 100)) if appeared else 0

                stotals = {}
                for m in marks:
                    sid   = m.student_id
                    score = m.lab_total() if m.exam_type == "lab" else m.theory_total()
                    if sid not in stotals: stotals[sid] = {"student": m.student, "total": score}
                    else: stotals[sid]["total"] += score

                avg   = round(sum(v["total"] for v in stotals.values()) / len(stotals), 1) if stotals else 0
                tlist = [(v["student"], round(v["total"], 1)) for v in stotals.values()]
                tlist.sort(key=lambda x: x[1], reverse=True)

                d_all_toppers.extend(tlist)
                d_total_passed   += passed
                d_total_appeared += appeared

                d_analytics.append({
                    "subject":   subject,
                    "appeared":  appeared,
                    "passed":    passed,
                    "failed":    failed,
                    "pass_rate": pass_rate,
                    "avg":       avg,
                    "toppers":   tlist[:3],
                })

            if not d_analytics:
                continue

            d_all_toppers.sort(key=lambda x: x[1], reverse=True)
            dept_wise.append({
                "dept":           d,
                "analytics":      d_analytics,
                "overall_pass":   round(sum(a["pass_rate"] for a in d_analytics) / len(d_analytics)),
                "overall_avg":    round(sum(a["avg"] for a in d_analytics) / len(d_analytics), 1),
                "total_passed":   d_total_passed,
                "total_appeared": d_total_appeared,
                "total_failed":   d_total_appeared - d_total_passed,
                "toppers":        d_all_toppers[:3],
                "students":       User.objects.filter(
                    userprofile__role="student",
                    userprofile__department=d
                ).count(),
            })

    return render(request, "marks/analytics.html", {
        "analytics":        analytics,
        "semester_choices": SEMESTER_CHOICES,
        "role":             role,
        "dept":             dept_filter,
        "semester_filter":  semester_filter,
        "all_depts":        ['CSE', 'ECE', 'AIML', 'IT', 'CIVIL', 'MECH', 'EEE'],
        "is_student":       role == "student",
        "dept_summary":     dept_summary,
        "dept_comparison":  dept_comparison,
        "dept_wise":        dept_wise,
    })
def notify_marks_posted(students, subject, exam_type):
    from core.models import Notification
    from django.core.mail import send_mail
    from django.conf import settings

    for student in students:
        student_name = student.get_full_name() or student.username

        # ── In-app Notification ─────────────────────
        Notification.objects.update_or_create(
            user=student,
            title=f"📊 Marks Posted — {subject.name}",
            defaults={
                "message": (
                    f"Your {exam_type.upper()} marks for {subject.name} "
                    f"have been uploaded. Check now."
                ),
                "link": "/marks/my/",
                "is_read": False,
            }
        )

        # ── Email Notification ─────────────────────
        if student.email:
            try:
                send_mail(
                    subject=f"[CampusIQ] Marks Uploaded — {subject.name}",
                    message=(
                        f"Hello {student_name},\n\n"
                        f"Your marks have been successfully uploaded.\n\n"
                        f"Subject    : {subject.name}\n"
                        f"Department : {subject.department}\n"
                        f"Semester   : {subject.semester}\n"
                        f"Exam Type  : {exam_type.upper()}\n\n"
                        f"You can now check your marks in CampusIQ.\n"
                        f"http://192.168.37.1:8000/marks/my/\n\n"
                        f"Regards,\nCampusIQ Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[student.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"[MARKS EMAIL ERROR] {e}")