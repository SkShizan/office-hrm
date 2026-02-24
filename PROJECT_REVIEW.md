# Office HRM Project Review (Quick Audit)

## 1) Confirmed Bugs / Risky Behaviors

1. **Destructive actions are not limited to POST**
   - `delete_employee` deletes records without checking HTTP method, so a GET request can trigger a delete.
   - `action_leave` also performs approve/reject side effects without a strict POST check.
   - Impact: accidental clicks, crawlers, or CSRF-style link attacks can change state.

2. **Task assignment endpoint lacks authorization checks**
   - In `handle_track_actions`, `add_task` can run for any `user_id` and does not verify whether the current user is allowed to assign tasks to that user.
   - Impact: any authenticated user could assign tasks to unrelated employees if they know IDs.

3. **Cross-company integrity holes in employee updates**
   - `approve_employee` / `edit_employee` fetch `Team` and `reports_to` by raw ID (`Team.objects.get(id=team_id)` / `User.objects.get(id=reports_to_id)`) without company scoping.
   - Impact: wrong-company linking, data leakage, and possible integrity errors.

4. **Production security defaults are unsafe in settings**
   - Hard-coded `SECRET_KEY`, `DEBUG=True`, and empty `ALLOWED_HOSTS` are committed directly in settings.
   - Impact: insecure production posture unless manually overridden.

5. **OTP flow lacks expiry/rate-limit controls**
   - OTP is stored in plain text and compared directly, but no expiration timestamp, resend cooldown, or retry limit exists.
   - Impact: brute-force risk and weak verification hardening.

6. **Error handling is print-based for email failures**
   - SMTP and send failures are caught and only printed (`print(...)`) with no user-facing fallback and no structured logging.
   - Impact: silent operational failures and difficult debugging.

## 2) Error / Quality Signals

1. **Environment reproducibility issue**
   - Running `python manage.py check` fails because Django is not installed in this environment.
   - Add a pinned `requirements.txt` or lockfile and setup instructions.

2. **No meaningful automated tests yet**
   - `accounts/tests.py` and `dashboard/tests.py` currently contain no coverage.
   - Business-critical flows (approval, leave deduction, attendance marking, OTP) are unprotected.

## 3) UI/UX and Design Improvement Opportunities

1. **Inline styles across templates**
   - Large per-template `<style>` blocks reduce consistency and make iteration hard.
   - Move shared design tokens/components to static CSS files (`base`, `auth`, `dashboard`, etc.).

2. **Missing explicit error rendering near fields**
   - Several forms rely on `form.as_p`; this often hides contextual validation feedback quality.
   - Improve with explicit field rendering, inline errors, and helper text.

3. **Role-based navigation clarity**
   - Navigation/actions could better reflect role permissions with disabled states and short permission hints.
   - This reduces failed attempts and confusion for employees vs managers vs HR.

4. **Mobile-first refinement**
   - Layout has a responsive section, but dashboards are dense. Introduce collapsible panels, sticky action buttons, and simplified mobile cards for attendance/track-sheet.

5. **Accessibility pass needed**
   - Add visible keyboard focus styles, ARIA labels for icon-only elements, and improve color contrast on muted text sections.

## 4) Feature Suggestions (High ROI)

1. **Attendance insights dashboard**
   - Monthly trend charts (late marks, absences, leave usage).
   - Filters by team/role with CSV export.

2. **Structured approval engine**
   - Multi-step approvals (TL -> Manager -> HR) with SLA reminders.
   - Escalation if pending for N days.

3. **Notifications center improvements**
   - Real-time badge count, read/unread bulk actions, and event categories.

4. **Audit trail & compliance logs**
   - Track who changed role/team/salary/attendance and when.
   - Essential for HR/legal accountability.

5. **Self-service profile and document vault**
   - Employee profile completeness checks.
   - Document upload (ID, offer letter, payslips) with role-based access.

## 5) Suggested Fix Order

1. Security and authorization hardening (POST-only mutating views, permission checks, company scoping).
2. OTP hardening and proper email/logging resilience.
3. Test coverage for critical workflows.
4. CSS/component system cleanup and accessibility.
5. Advanced analytics and workflow features.
