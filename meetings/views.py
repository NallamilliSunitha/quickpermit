import uuid
import json
import os
import base64
from datetime import timedelta
from reportlab.lib.utils import ImageReader
from core.utils import create_notification

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import landscape, A4
from PIL import Image
import io
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive



from .models import (
    Meeting, MeetingParticipant, MeetingRecipient,
    MeetingCheckpoint, CheckpointPresence,
    MeetingTranscript, MeetingWhiteboard
)
from .permissions import (
    can_create_meeting,
    can_view_hod_dashboard,
    get_department,
    get_role,
)

@login_required
def create_meeting(request):
    role = get_role(request.user)

    if not can_create_meeting(request.user):
        return redirect("dashboard")

    if request.method == "POST":
        title          = request.POST.get("title")
        meeting_type   = request.POST.get("meeting_type")
        scheduled_at   = request.POST.get("scheduled_at")
        audience_type  = request.POST.get("audience_type")
        department     = request.POST.get("department")
        departments    = request.POST.getlist("departments")
        college        = request.POST.get("college")  # Added college selection
        target_ids_raw = request.POST.get("target_ids", "")
        dept           = request.user.userprofile.department

        # ── Semester & Section (only used when audience includes students) ──
        semester = request.POST.get("semester", "").strip() or None
        section  = request.POST.get("section", "").strip()  or None

        # ONE create only
        meeting = Meeting.objects.create(
            title=title,
            meeting_type=meeting_type,
            created_by=request.user,
            department=dept,
            room_name="CampusIQ-" + str(uuid.uuid4())[:8],
            scheduled_at=scheduled_at,
            audience_type=audience_type,
            duration_minutes=int(request.POST.get("duration_minutes", 30)),
        )

        # ── Helper: apply semester, section & college filters to a student queryset ──
        def filter_students(qs):
            if college:
                qs = qs.filter(userprofile__college=college)
            if semester:
                qs = qs.filter(userprofile__semester=semester)
            if section:
                qs = qs.filter(userprofile__section=section)
            return qs

        recipients = User.objects.none()

        if role in ["staff", "proctor"]:
            dept = request.user.userprofile.department
            if audience_type == "students":
                recipients = filter_students(User.objects.filter(
                    userprofile__role="student",
                    userprofile__department=dept
                ))

        elif role == "hod":
            dept = request.user.userprofile.department
            if audience_type == "students":
                recipients = filter_students(User.objects.filter(
                    userprofile__role="student",
                    userprofile__department=dept
                ))
            elif audience_type == "staff":
                recipients = User.objects.filter(
                    userprofile__role__in=["staff", "proctor"],
                    userprofile__department=dept
                )
            elif audience_type == "both":
                students = filter_students(User.objects.filter(
                    userprofile__role="student",
                    userprofile__department=dept
                ))
                staff = User.objects.filter(
                    userprofile__role__in=["staff", "proctor"],
                    userprofile__department=dept
                )
                combined_ids = list(students.values_list("id", flat=True)) + \
                               list(staff.values_list("id", flat=True))
                recipients = User.objects.filter(id__in=combined_ids)

        elif role == "dean":
            dept_list = departments
            if audience_type == "students":
                recipients = filter_students(User.objects.filter(
                    userprofile__role="student",
                    userprofile__department__in=dept_list
                ))
            elif audience_type == "staff":
                recipients = User.objects.filter(
                    userprofile__role__in=["staff", "proctor"],
                    userprofile__department__in=dept_list
                )
            elif audience_type == "hod":
                recipients = User.objects.filter(
                    userprofile__role="hod",
                    userprofile__department__in=dept_list
                )
            elif audience_type == "hod_staff":
                recipients = User.objects.filter(
                    userprofile__role__in=["hod", "staff", "proctor"],
                    userprofile__department__in=dept_list
                )
            elif audience_type == "hod_students":
                students = filter_students(User.objects.filter(
                    userprofile__role="student",
                    userprofile__department__in=dept_list
                ))
                hods = User.objects.filter(
                    userprofile__role="hod",
                    userprofile__department__in=dept_list
                )
                combined_ids = list(students.values_list("id", flat=True)) + \
                               list(hods.values_list("id", flat=True))
                recipients = User.objects.filter(id__in=combined_ids)
            elif audience_type == "students_staff":
                students = filter_students(User.objects.filter(
                    userprofile__role="student",
                    userprofile__department__in=dept_list
                ))
                staff = User.objects.filter(
                    userprofile__role__in=["staff", "proctor"],
                    userprofile__department__in=dept_list
                )
                combined_ids = list(students.values_list("id", flat=True)) + \
                               list(staff.values_list("id", flat=True))
                recipients = User.objects.filter(id__in=combined_ids)
            elif audience_type == "all":
                recipients = User.objects.filter(
                    userprofile__department__in=dept_list
                )

        elif role == "principal":
            if audience_type == "students":
                recipients = filter_students(
                    User.objects.filter(userprofile__role="student")
                )
            elif audience_type == "staff":
                recipients = User.objects.filter(
                    userprofile__role__in=["staff", "proctor"]
                )
            elif audience_type == "hod":
                recipients = User.objects.filter(userprofile__role="hod")
            elif audience_type == "dean":
                recipients = User.objects.filter(userprofile__role="dean")
            elif audience_type == "students_staff":
                students = filter_students(
                    User.objects.filter(userprofile__role="student")
                )
                staff = User.objects.filter(
                    userprofile__role__in=["staff", "proctor"]
                )
                combined_ids = list(students.values_list("id", flat=True)) + \
                               list(staff.values_list("id", flat=True))
                recipients = User.objects.filter(id__in=combined_ids)
            elif audience_type == "hod_staff":
                recipients = User.objects.filter(
                    userprofile__role__in=["hod", "staff", "proctor"]
                )
            elif audience_type == "dean_staff":
                recipients = User.objects.filter(
                    userprofile__role__in=["dean", "staff", "proctor"]
                )
            elif audience_type == "dean_hod":
                recipients = User.objects.filter(
                    userprofile__role__in=["dean", "hod"]
                )
            elif audience_type == "all":
                recipients = User.objects.exclude(id=request.user.id)

        if target_ids_raw:
            ids = [x.strip() for x in target_ids_raw.split(",")]
            recipients = recipients.filter(
                Q(userprofile__roll_number__in=ids) | Q(username__in=ids)
            )

        for user in recipients:
            MeetingRecipient.objects.get_or_create(meeting=meeting, user=user)

        # Create 3 checkpoints at 10, 20, 30 minutes
        if meeting.scheduled_at:
            from django.utils.dateparse import parse_datetime
            base_time = meeting.scheduled_at
            if isinstance(base_time, str):
                base_time = parse_datetime(base_time)
            if base_time:
                for i, minutes in enumerate([10, 20, 30], start=1):
                    MeetingCheckpoint.objects.create(
                        meeting=meeting,
                        checkpoint_no=i,
                        scheduled_at=base_time + timedelta(minutes=minutes)
                    )

        # Send email invites
        join_link  = f"https://sunitha11.pythonanywhere.com/meetings/join/{meeting.id}/"
        email_list = [u.email for u in recipients if u.email]

        if request.user.email and request.user.email not in email_list:
            email_list.append(request.user.email)

        if email_list:
            subject = f"CampusIQ Meeting Invitation: {meeting.title}"
            context = {
                "title":        meeting.title,
                "department":   department if department else ", ".join(departments),
                "scheduled_at": meeting.scheduled_at,
                "duration":     meeting.duration_minutes,
                "join_link":    join_link
            }
            html_content = render_to_string("meetings/email_invite.html", context)
            email = EmailMultiAlternatives(
                subject, "Meeting Invitation",
                settings.DEFAULT_FROM_EMAIL, email_list
            )
            email.attach_alternative(html_content, "text/html")
            try:
                email.send()
            except Exception as e:
                print("Email error:", e)

        for user in recipients:
            create_notification(
                user=user,
                title="New Meeting Invitation",
                message=f"You are invited to '{meeting.title}' scheduled on {meeting.scheduled_at}.",
                link=f"/meetings/join/{meeting.id}/"
            )

        return redirect("meeting_history")

    return render(request, "meetings/create.html", {"role": role})
@login_required
def start_meeting(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.user != meeting.created_by:
        return HttpResponseForbidden("Only the creator can start the meeting.")

    if meeting.status == "scheduled":
        meeting.status   = "ongoing"
        meeting.started_at = timezone.now()
        meeting.save()

    return render(request, "meetings/room.html", {
        "meeting": meeting,
        "is_creator": True,
    })

def join_meeting(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if not request.user.is_authenticated:
        return redirect(f"/accounts/login/?next=/meetings/join/{meeting.id}/")

    is_creator = request.user == meeting.created_by
    is_invited = MeetingRecipient.objects.filter(
        meeting=meeting, user=request.user
    ).exists()

    if not is_creator and not is_invited:
        return render(request, "meetings/not_invited.html", {"meeting": meeting})

    if meeting.status == "scheduled":
        return render(request, "meetings/not_started.html", {
            "meeting": meeting,
            "is_creator": is_creator,
        })

    if meeting.status == "completed":
        return redirect("meeting_summary", meeting.id)

    if meeting.status == "cancelled":
        return render(request, "meetings/cancel_meeting.html", {"meeting": meeting})

    participant, _ = MeetingParticipant.objects.get_or_create(
        meeting=meeting, user=request.user
    )

    # Reset left_early if they rejoin
    if participant.left_early:
        participant.left_early = False
        participant.left_at = None
        participant.save(update_fields=["left_early", "left_at"])

    participant.mark_join()

    return render(request, "meetings/room.html", {
        "meeting": meeting,
        "is_creator": is_creator,
    })


@login_required
def meeting_detail(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    is_creator = request.user == meeting.created_by
    is_invited = MeetingRecipient.objects.filter(
        meeting=meeting, user=request.user
    ).exists()

    if not is_creator and not is_invited:
        return render(request, "meetings/not_invited.html", {"meeting": meeting})

    if meeting.status == "scheduled":
        return render(request, "meetings/not_started.html", {
            "meeting": meeting,
            "is_creator": is_creator,
        })

    if meeting.status == "completed":
        return redirect("meeting_summary", meeting.id)

    return redirect("join_meeting", meeting.id)


@login_required
def heartbeat(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)

    participant, _ = MeetingParticipant.objects.get_or_create(
        meeting=meeting, user=request.user
    )
    participant.last_seen = timezone.now()
    participant.save(update_fields=["last_seen"])

    now         = timezone.now()
    checkpoints = MeetingCheckpoint.objects.filter(meeting=meeting)

    for cp in checkpoints:
        diff = abs((now - cp.scheduled_at).total_seconds())
        if diff <= 90:
            CheckpointPresence.objects.get_or_create(
                checkpoint=cp,
                user=request.user,
                defaults={"present": True}
            )

    return JsonResponse({"ok": True})


@login_required
def end_meeting(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.user != meeting.created_by:
        return HttpResponseForbidden("Only creator can end the meeting")

    meeting.status   = "completed"
    meeting.ended_at = timezone.now()
    meeting.save(update_fields=["status", "ended_at"])
    invited = MeetingRecipient.objects.filter(meeting=meeting).select_related("user")
    for r in invited:
        create_notification(
        user=r.user,
        title="Meeting Ended",
        message=f"Meeting '{meeting.title}' has ended. View the summary.",
        link=f"/meetings/summary/{meeting.id}/"
    )

    MeetingParticipant.objects.filter(
        meeting=meeting, left_at__isnull=True
    ).update(left_at=timezone.now())

    # Generate AI summary
    try:
        summary = generate_ai_summary(meeting)
        if summary:
            meeting.ai_summary = summary
            meeting.save(update_fields=["ai_summary"])
    except Exception as e:
        print("Summary generation error:", e)

    return JsonResponse({"ok": True})

@login_required
def mark_left(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.method == "POST":
        participant = MeetingParticipant.objects.filter(
            meeting=meeting, user=request.user
        ).first()
        if participant and not participant.left_at:
            participant.left_at    = timezone.now()
            participant.left_early = True
            participant.save(update_fields=["left_at", "left_early"])

    return JsonResponse({"ok": True})


@login_required
def save_transcript(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.method == "POST":
        data = json.loads(request.body)
        MeetingTranscript.objects.update_or_create(
            meeting=meeting,
            defaults={"content": json.dumps(data.get("transcript", []))}
        )

    return JsonResponse({"ok": True})


@login_required
def save_whiteboard(request, id):
    if request.method != "POST":
        return JsonResponse({"ok": False})

    meeting = get_object_or_404(Meeting, id=id)

    if request.user != meeting.created_by:
        return JsonResponse({"ok": False, "error": "Not allowed"})

    import json
    data = json.loads(request.body)

    current_image = data.get("image", "")
    all_pages     = data.get("all_pages", [])

    wb, _ = MeetingWhiteboard.objects.get_or_create(meeting=meeting)
    wb.image_data = json.dumps({
        "pages":   all_pages,
        "current": current_image
    })
    wb.save()
    return JsonResponse({"ok": True})


@login_required
def meeting_summary(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    is_creator = request.user == meeting.created_by
    is_invited = MeetingRecipient.objects.filter(
        meeting=meeting, user=request.user
    ).exists()

    if not is_creator and not is_invited:
        return HttpResponseForbidden("Not invited.")

    recipients        = MeetingRecipient.objects.filter(meeting=meeting).select_related("user")
    total_checkpoints = MeetingCheckpoint.objects.filter(
        meeting=meeting,
        scheduled_at__lte=(meeting.ended_at or timezone.now())
    ).count()

    report_rows      = []
    attended_count   = 0
    left_early_count = 0
    absent_count     = 0

    for r in recipients:
        count   = CheckpointPresence.objects.filter(
            checkpoint__meeting=meeting, user=r.user, present=True
        ).count()
        percent = round((count / total_checkpoints) * 100) if total_checkpoints else 0

        if count == total_checkpoints and total_checkpoints > 0:
            label = "Excellent"; attended_count += 1
        elif total_checkpoints and count >= total_checkpoints * 0.66:
            label = "Good"; attended_count += 1
        elif total_checkpoints and count >= total_checkpoints * 0.33:
            label = "Low"; attended_count += 1
        else:
            label = "Absent"; absent_count += 1

        participant = MeetingParticipant.objects.filter(
            meeting=meeting, user=r.user
        ).first()

        left_early = False
        left_at    = None
        if participant:
            left_early = participant.left_early
            left_at    = participant.left_at
            if left_early:
                left_early_count += 1

        report_rows.append({
            "user":       r.user,
            "count":      count,
            "percent":    percent,
            "label":      label,
            "left_early": left_early,
            "left_at":    left_at,
        })

    transcript_obj = MeetingTranscript.objects.filter(meeting=meeting).first()
    transcript     = []
    if transcript_obj:
        try:
            transcript = json.loads(transcript_obj.content)
        except Exception:
            transcript = []

    whiteboard_obj = MeetingWhiteboard.objects.filter(meeting=meeting).first()
    whiteboard_image = whiteboard_obj.image_data if whiteboard_obj else None

    return render(request, "meetings/meeting_summary.html", {
        "meeting":           meeting,
        "report_rows":       report_rows,
        "total_checkpoints": total_checkpoints,
        "total_participants": recipients.count(),
        "attended_count":    attended_count,
        "left_early_count":  left_early_count,
        "absent_count":      absent_count,
        "transcript":        transcript,
        "whiteboard_image":  whiteboard_image,
        "is_creator":        is_creator,
    })


@login_required
def download_whiteboard_pdf(request, id):
    meeting = get_object_or_404(Meeting, id=id)
    wb = MeetingWhiteboard.objects.filter(meeting=meeting).first()

    if not wb or not wb.image_data:
        return HttpResponse("No whiteboard data", status=404)

    import json
    from io import BytesIO
    from PIL import Image
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import landscape, A4

    try:
        data = json.loads(wb.image_data)
        if isinstance(data, dict):
            all_pages = data.get("pages", [])
            current   = data.get("current", "")
            if current:
                all_pages.append(current)
        else:
            # Old format — single image string
            all_pages = [wb.image_data]
    except:
        all_pages = [wb.image_data]

    if not all_pages:
        return HttpResponse("No whiteboard data", status=404)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    w, h = landscape(A4)

    for i, page_data in enumerate(all_pages):
        try:
            # Remove base64 header
            if "," in page_data:
                page_data = page_data.split(",")[1]

            import base64
            img_bytes = base64.b64decode(page_data)
            img = Image.open(BytesIO(img_bytes))

            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            if i > 0:
                c.showPage()

            # Page number
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.drawString(20, h - 20, f"Page {i+1} of {len(all_pages)}  |  {meeting.title}")

            c.drawImage(
                ImageReader(img_buffer),
                10, 10,
                width=w - 20,
                height=h - 40,
                preserveAspectRatio=True
            )
        except Exception as e:
            print(f"Page {i+1} error:", e)
            continue

    c.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="whiteboard_{meeting.id}.pdf"'
    return response
@login_required
def download_attendance_pdf(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.user != meeting.created_by and get_role(request.user) not in ["hod", "dean", "principal"]:
        return HttpResponseForbidden("Not allowed")

    recipients        = MeetingRecipient.objects.filter(meeting=meeting).select_related("user")
    total_checkpoints = MeetingCheckpoint.objects.filter(
        meeting=meeting,
        scheduled_at__lte=(meeting.ended_at or timezone.now())
    ).count()

    buffer = io.BytesIO()
    c      = rl_canvas.Canvas(buffer, pagesize=A4)
    pw, ph = A4
    y      = ph - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Attendance Report")
    y -= 30
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Meeting : {meeting.title}")
    y -= 20
    c.drawString(50, y, f"Dept    : {meeting.department}")
    y -= 20
    c.drawString(50, y, f"Date    : {meeting.scheduled_at}")
    y -= 40

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50,  y, "Name")
    c.drawString(220, y, "Username")
    c.drawString(340, y, "Checkpoints")
    c.drawString(440, y, "Status")
    c.drawString(510, y, "Left Early")
    y -= 20

    c.setFont("Helvetica", 10)
    for r in recipients:
        count   = CheckpointPresence.objects.filter(
            checkpoint__meeting=meeting, user=r.user, present=True
        ).count()
        percent = round((count / total_checkpoints) * 100) if total_checkpoints else 0

        if count == total_checkpoints and total_checkpoints > 0:
            label = "Excellent"
        elif total_checkpoints and count >= total_checkpoints * 0.66:
            label = "Good"
        elif total_checkpoints and count >= total_checkpoints * 0.33:
            label = "Low"
        else:
            label = "Absent"

        participant = MeetingParticipant.objects.filter(meeting=meeting, user=r.user).first()
        left_early  = participant.left_early if participant else False

        c.drawString(50,  y, r.user.get_full_name() or r.user.username)
        c.drawString(220, y, r.user.username)
        c.drawString(340, y, f"{count}/{total_checkpoints} ({percent}%)")
        c.drawString(440, y, label)
        c.drawString(510, y, "Yes" if left_early else "No")
        y -= 18

        if y < 80:
            c.showPage()
            y = ph - 50

    c.save()
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="attendance_{meeting.id}.pdf"'
    return response


@login_required
def live_attendance(request, id):
    meeting      = get_object_or_404(Meeting, id=id)
    participants = MeetingParticipant.objects.filter(meeting=meeting).select_related("user")

    data = []
    for p in participants:
        data.append({
            "user":       p.user.get_full_name() or p.user.username,
            "joined":     p.joined_at.isoformat() if p.joined_at else None,
            "last_seen":  p.last_seen.isoformat() if p.last_seen else None,
            "left_early": p.left_early,
        })

    return JsonResponse({"participants": data})


@login_required
def meeting_status(request, id):
    meeting = get_object_or_404(Meeting, id=id)
    return JsonResponse({"status": meeting.status})


@login_required
def meeting_history(request):
    role     = get_role(request.user)
    meetings = Meeting.objects.all().select_related("created_by").order_by("-scheduled_at", "-created_at")

    if role == "student":
        meetings = meetings.filter(recipients__user=request.user).distinct()
    elif role in ["staff", "proctor"]:
        meetings = meetings.filter(
            Q(created_by=request.user) | Q(recipients__user=request.user)
        ).distinct()
    elif role == "hod":
        meetings = meetings.filter(department=get_department(request.user))
    elif role in ["dean", "principal"]:
        pass
    else:
        meetings = meetings.none()

    status       = (request.GET.get("status") or "").strip()
    meeting_type = (request.GET.get("type") or "").strip()
    dept         = (request.GET.get("department") or "").strip()
    q            = (request.GET.get("q") or "").strip()

    if status:       meetings = meetings.filter(status=status)
    if meeting_type: meetings = meetings.filter(meeting_type=meeting_type)
    if dept:         meetings = meetings.filter(department__iexact=dept)
    if q:
        meetings = meetings.filter(
            Q(title__icontains=q) |
            Q(created_by__username__icontains=q) |
            Q(created_by__first_name__icontains=q) |
            Q(created_by__last_name__icontains=q)
        )

    return render(request, "meetings/history.html", {
        "meetings":      meetings,
        "status":        status,
        "meeting_type":  meeting_type,
        "dept":          dept,
        "q":             q,
        "now":           timezone.now(),
    })


@login_required
def cancel_meeting(request, id):
    meeting = get_object_or_404(Meeting, id=id)

    if request.user != meeting.created_by:
        return HttpResponseForbidden("Only creator can cancel this meeting.")

    if meeting.status in ["ongoing", "completed", "cancelled"]:
        return HttpResponseForbidden("This meeting cannot be cancelled now.")

    if meeting.scheduled_at and timezone.now().date() > meeting.scheduled_at.date():
        return HttpResponseForbidden("Past meetings cannot be cancelled.")

    if request.method == "POST":
        comment = (request.POST.get("comment") or "").strip()
        if not comment:
            return render(request, "meetings/cancel_meeting.html", {
                "meeting": meeting,
                "error": "Please enter cancellation reason."
            })

        meeting.status = "cancelled"
        meeting.cancel_comment = comment
        meeting.save(update_fields=["status", "cancel_comment"])

        # ✅ FIXED: DEFINE recipients FIRST
        recipients = User.objects.filter(meetingrecipient__meeting=meeting).distinct()

        for u in recipients:
            create_notification(
                user=u,
                title="Meeting Cancelled",
                message=f"Meeting '{meeting.title}' has been cancelled. Reason: {comment}",
                link=f"/modules/meetings/"
            )

        email_list = [u.email for u in recipients if u.email]

        if email_list:
            send_mail(
                f"Meeting Cancelled: {meeting.title}",
                f"The meeting '{meeting.title}' has been cancelled.\n\nReason: {comment}\n\nRegards,\nCampusIQ",
                settings.DEFAULT_FROM_EMAIL,
                email_list,
                fail_silently=True
            )

        return redirect("dashboard")

    return render(request, "meetings/cancel_meeting.html", {"meeting": meeting})


@login_required
def hod_meetings_dashboard(request):
    if not can_view_hod_dashboard(request.user):
        return redirect("dashboard")

    role = get_role(request.user)
    dept = get_department(request.user)

    meetings          = Meeting.objects.all()
    if role == "hod":
        meetings      = meetings.filter(department=dept)

    total_meetings    = meetings.count()
    total_participants = MeetingParticipant.objects.filter(meeting__in=meetings).count()
    avg_score         = MeetingParticipant.objects.filter(
        meeting__in=meetings
    ).aggregate(Avg("participation_score"))["participation_score__avg"] or 0
    type_stats        = meetings.values("meeting_type").annotate(total=Count("id")).order_by("-total")

    return render(request, "meetings/hod_dashboard.html", {
        "total_meetings":     total_meetings,
        "total_participants": total_participants,
        "avg_score":          round(avg_score, 2),
        "type_stats":         type_stats,
        "role":               role,
        "dept":               dept,
    })
def generate_ai_summary(meeting):
    try:
        from groq import Groq
        from django.conf import settings
        import re

        transcripts = MeetingTranscript.objects.filter(meeting=meeting).order_by("updated_at")
        if not transcripts.exists():
            return None

        transcript_text = ""
        for t in transcripts:
            try:
                import json
                entries = json.loads(t.content)
                for e in entries:
                    transcript_text += f"{e.get('speaker', 'Unknown')}: {e.get('text', '')}\n"
            except:
                transcript_text += str(t.content) + "\n"

        if not transcript_text.strip():
            return None

        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert meeting summarizer. Generate clear, structured summaries. Do NOT use emojis or special unicode characters."
                },
                {
                    "role": "user",
                    "content": f"""Summarize this meeting transcript:

Meeting: {meeting.title}
Department: {meeting.department}

Transcript:
{transcript_text}

Generate a structured summary with these sections:
## Overview
## Key Points Discussed
## Decisions Made
## Action Items
## Key Takeaway

Keep it professional. Do NOT use emojis."""
                }
            ]
        )

        summary = response.choices[0].message.content.strip()

        # Remove all emojis and non-BMP unicode characters
        summary = re.sub(r'[^\x00-\xFFFF]', '', summary)
        # Remove any remaining 4-byte unicode
        summary = summary.encode('utf-8', 'ignore').decode('utf-8')

        return summary

    except Exception as e:
        print("Summary generation error:", e)
        return None