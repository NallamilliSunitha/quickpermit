from io import BytesIO
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from accounts.models import UserProfile
from permissions.models import PermissionRequest
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.utils import timezone

@login_required
def permission_report_pdf(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    role = (profile.role or "").strip().lower() if profile else ""
    if role not in ("hod", "dean", "principal"):
        return HttpResponseForbidden("Only HOD/Dean/Principal can download reports")

    dept = profile.department if profile else ""
    qs = PermissionRequest.objects.filter(student__userprofile__department=dept).order_by("-applied_at")[:200]

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, h - 50, f"Permission Report - {dept}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, h - 70, f"Generated: {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}")

    y = h - 100
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Code")
    pdf.drawString(140, y, "Student")
    pdf.drawString(260, y, "Title")
    pdf.drawString(430, y, "Status")
    y -= 15

    pdf.setFont("Helvetica", 9)
    for r in qs:
        if y < 60:
            pdf.showPage()
            y = h - 60
            pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, (r.request_code or "")[:12])
        pdf.drawString(140, y, (r.student.username or "")[:15])
        pdf.drawString(260, y, (r.title or "")[:28])
        pdf.drawString(430, y, (r.status or "").upper())
        y -= 14

    pdf.showPage()
    pdf.save()
    buf.seek(0)

    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="permission_report_{dept}.pdf"'
    return resp
