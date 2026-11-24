from django.contrib import admin
from .models import Attendance, LeaveBalance, LeaveRequest

admin.site.register(LeaveBalance)
admin.site.register(LeaveRequest)
admin.site.register(Attendance)
