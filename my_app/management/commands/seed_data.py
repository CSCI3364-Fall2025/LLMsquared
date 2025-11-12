# my_app/management/commands/seed_data.py
import json
import math
import random
from datetime import datetime, date, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


from my_app.models import (
    User,
    Course,
    CourseMember,
    Team,
    TeamMember,
    Assessment,
    AssessmentQuestion,
    AssessmentResponse,
    TeamAssessmentAnalysis,
    QuestionAnalysisCache,
    OpenEndedToneAnalysis,
)

LEVEL_CONFIG = {
    1: {"courses": 150,  "students_min": 30, "students_max": 80,  "team_min": 4, "team_max": 8},
    2: {"courses": 700,  "students_min": 30, "students_max": 80,  "team_min": 4, "team_max": 6},
    3: {"courses": 2000, "students_min": 30, "students_max": 100, "team_min": 4, "team_max": 6},
}

def partition_into_teams(num_students: int, min_team: int, max_team: int, rng: random.Random):
    if num_students <= 0:
        return []
    if num_students < min_team:
        return [num_students]
    lower_bound = max(1, num_students // max_team)
    approx_teams = max(1, round(num_students / ((min_team + max_team) / 2)))
    team_count = max(lower_bound, approx_teams)
    sizes = [min_team] * team_count
    assigned = min_team * team_count
    while assigned < num_students:
        idxs = list(range(team_count))
        rng.shuffle(idxs)
        progressed = False
        for i in idxs:
            if sizes[i] < max_team and assigned < num_students:
                sizes[i] += 1
                assigned += 1
                progressed = True
            if assigned >= num_students:
                break
        if not progressed:
            remain = num_students - assigned
            if remain <= 0:
                break
            add = min(max(remain, min_team), max_team)
            sizes.append(add)
            assigned += add
            team_count += 1
    if assigned > num_students:
        overflow = assigned - num_students
        for i in range(team_count - 1, -1, -1):
            take = min(overflow, sizes[i] - min_team)
            sizes[i] -= take
            overflow -= take
            if overflow == 0:
                break
    assert sum(sizes) == num_students, f"partition failed: {sizes} vs {num_students}"
    return sizes

def biased_score(rng: random.Random, max_score: int = 5):
    # Triangular bias toward higher scores
    a = rng.triangular(1, max_score, max_score)
    return max(1, min(max_score, int(round(a))))

def chunk_list(items, n):
    for i in range(0, len(items), n):
        yield items[i:i+n]


class Command(BaseCommand):
    help = (
        "Seed database with teachers, students, course memberships, teams, "
        "assessments, questions, and peer responses.\n\n"
        "Examples:\n"
        "  python manage.py seed_data --level 1 --semester Spring --year 2025 --purge\n"
        "  python manage.py seed_data --level 2 --semester Fall --year 2025 --export-csv ./seed_out\n"
    )

    def add_arguments(self, parser):
        parser.add_argument("--level", type=int, choices=[1, 2, 3], default=1)
        parser.add_argument("--semester", type=str, choices=["Spring", "Fall"], default="Spring")
        parser.add_argument("--year", type=int, default=timezone.now().year)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--purge", action="store_true", help="Delete existing data before seeding")
        parser.add_argument("--export-csv", type=str, default=None, help="Optional: dump CSVs to this directory")

    def handle(self, *args, **opt):
        rng = random.Random(opt["seed"])

        if opt["purge"]:
            self._purge()

        cfg = LEVEL_CONFIG[opt["level"]]
        courses_target = cfg["courses"]
        students_min, students_max = cfg["students_min"], cfg["students_max"]
        team_min, team_max = cfg["team_min"], cfg["team_max"]

        export = opt["export_csv"] is not None
        if export:
            outdir = Path(opt["export_csv"])
            outdir.mkdir(parents=True, exist_ok=True)
            csv_rows = {
                "users": [],
                "courses": [],
                "course_members": [],
                "teams": [],
                "team_members": [],
                "assessments": [],
                "assessment_questions": [],
                "assessment_responses": [],
            }

        open_at  = datetime(date.today().year, 10, 1, 9, 0, tzinfo=timezone.get_current_timezone())
        close_at = datetime(date.today().year, 10, 31, 23, 59, tzinfo=timezone.get_current_timezone())

        progress_every = max(1, courses_target // 20)

        with transaction.atomic():
            for idx in range(courses_target):
                # teacher
                prof_email = f"teacher+{idx+1}@faculty.example.edu"
                teacher = User.objects.create(
                    email=prof_email,
                    name=f"Prof {idx+1}",
                    role="teacher",
                )
                if export:
                    csv_rows["users"].append([str(teacher.id), teacher.email, teacher.name, teacher.role])

                # course
                course_number = f"CS{1000 + idx:04d}"
                course = Course.objects.create(
                    course_number=course_number,
                    course_name=f"Course {course_number}",
                    course_semester=opt["semester"],
                    course_year=str(opt["year"]),
                    teacher=teacher,
                )
                if export:
                    csv_rows["courses"].append([
                        str(course.id), course.course_number, course.course_name,
                        course.course_semester, course.course_year, str(teacher.id)
                    ])

                # students
                num_students = rng.randint(students_min, students_max)
                students = [
                    User(email=f"student+{course.course_number}-{j+1}@student.example.edu",
                         name=f"Student {course.course_number}-{j+1}",
                         role="student")
                    for j in range(num_students)
                ]
                User.objects.bulk_create(students, batch_size=1000)
                students = list(User.objects.filter(
                    email__startswith=f"student+{course.course_number}-", role="student"
                ).order_by("email"))

                members = [CourseMember(course=course, user=s) for s in students]
                CourseMember.objects.bulk_create(members, batch_size=1000)
                members = list(CourseMember.objects.filter(course=course).select_related("user").order_by("id"))

                if export:
                    for cm in members:
                        csv_rows["course_members"].append([str(cm.id), str(course.id), str(cm.user.id)])

                # teams
                sizes = partition_into_teams(num_students, team_min, team_max, rng)
                rng.shuffle(members)
                pos = 0
                teams = []
                for tnum, sz in enumerate(sizes, start=1):
                    t = Team(course=course, team_name=f"Team {tnum:02d}")
                    teams.append(t)
                Team.objects.bulk_create(teams, batch_size=500)
                teams = list(Team.objects.filter(course=course).order_by("id"))

                tm_rows = []
                for team in teams:
                    pass
                # Assign members chunk-by-chunk
                team_members_to_create = []
                for t_idx, team in enumerate(teams):
                    sz = sizes[t_idx]
                    chunk = members[pos:pos+sz]
                    pos += sz
                    for cm in chunk:
                        team_members_to_create.append(TeamMember(team=team, course_member=cm))
                TeamMember.objects.bulk_create(team_members_to_create, batch_size=1000)

                if export:
                    for tm in TeamMember.objects.filter(team__course=course).select_related("team", "course_member"):
                        csv_rows["team_members"].append([str(tm.id), str(tm.team.id), str(tm.course_member.id)])

                # assessments 
                assess = Assessment.objects.create(
                    course=course,
                    title=f"{course.course_number} – Peer Review 1",
                    status="published",
                    publish_date=open_at,
                    due_date=close_at,
                    results_released=False,
                )
                if export:
                    csv_rows["assessments"].append([
                        str(assess.id), str(course.id), assess.title, assess.status,
                        assess.publish_date.isoformat() if assess.publish_date else "",
                        assess.due_date.isoformat() if assess.due_date else "",
                        str(assess.results_released)
                    ])

                likert_prompts = [
                    "Contributed fair share",
                    "Communicated effectively",
                    "Met deadlines",
                    "Showed leadership",
                    "Quality of work",
                ]
                questions = [
                    AssessmentQuestion(
                        assessment=assess, question_type="likert", content=p
                    ) for p in likert_prompts
                ]
                AssessmentQuestion.objects.bulk_create(questions, batch_size=20)
                questions = list(AssessmentQuestion.objects.filter(assessment=assess).order_by("id"))

                if export:
                    for q in questions:
                        csv_rows["assessment_questions"].append([
                            str(q.id), str(assess.id), q.question_type, q.content
                        ])

                # peer responses
                # Build team_id -> list[CourseMember]
                by_team = {}
                for tm in TeamMember.objects.filter(team__course=course).select_related("team", "course_member__user").order_by("team_id"):
                    by_team.setdefault(tm.team_id, []).append(tm.course_member)

                # Create responses
                responses_to_create = []
                for team_id, cms in by_team.items():
                    # each student evaluates every other
                    for i, cm_i in enumerate(cms):
                        for j, cm_j in enumerate(cms):
                            if i == j:
                                continue
                            answers = {}
                            for q in questions:
                                answers[str(q.id)] = biased_score(rng, 5)
                            responses_to_create.append(
                                AssessmentResponse(
                                    assessment=assess,
                                    from_user=cm_i.user,
                                    to_user=cm_j.user,
                                    answers=answers,
                                    submitted=True,
                                )
                            )
                AssessmentResponse.objects.bulk_create(responses_to_create, batch_size=1000)

                # progress
                if (idx + 1) % progress_every == 0 or (idx + 1) == courses_target:
                    self.stdout.write(self.style.NOTICE(
                        f"Seeded {idx+1}/{courses_target} courses ({(idx+1)/courses_target:.0%})"
                    ))

        if export:
            # write CSVs
            def write_csv(path, header, rows):
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(",".join(header) + "\n")
                    for r in rows:
                        line = ",".join(map(str, r))
                        f.write(line + "\n")

            write_csv(outdir / "users.csv", ["id", "email", "name", "role"], csv_rows["users"])
            write_csv(outdir / "courses.csv", ["id", "course_number", "course_name", "semester", "year", "teacher_id"], csv_rows["courses"])
            write_csv(outdir / "course_members.csv", ["id", "course_id", "user_id"], csv_rows["course_members"])
            write_csv(outdir / "teams.csv", ["id", "course_id", "team_name"], csv_rows["teams"])
            write_csv(outdir / "team_members.csv", ["id", "team_id", "course_member_id"], csv_rows["team_members"])
            write_csv(outdir / "assessments.csv", ["id", "course_id", "title", "status", "publish_date", "due_date", "results_released"], csv_rows["assessments"])
            write_csv(outdir / "assessment_questions.csv", ["id", "assessment_id", "question_type", "content"], csv_rows["assessment_questions"])
            write_csv(outdir / "assessment_responses.csv", ["id", "assessment_id", "from_user_id", "to_user_id", "answers", "submitted"], [
                [str(ar.id), str(ar.assessment_id), str(ar.from_user_id), str(ar.to_user_id), json.dumps(ar.answers), str(ar.submitted)]
                for ar in AssessmentResponse.objects.all().only("id","assessment_id","from_user_id","to_user_id","answers","submitted")
            ])
            manifest = {
                "level": opt["level"],
                "semester": f"{opt['semester']} {opt['year']}",
                "counts": {
                    "users": User.objects.count(),
                    "courses": Course.objects.count(),
                    "course_members": CourseMember.objects.count(),
                    "teams": Team.objects.count(),
                    "team_members": TeamMember.objects.count(),
                    "assessments": Assessment.objects.count(),
                    "assessment_questions": AssessmentQuestion.objects.count(),
                    "assessment_responses": AssessmentResponse.objects.count(),
                },
            }
            (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
            self.stdout.write(self.style.SUCCESS(f"CSV exported to {outdir}"))

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    def _purge(self):
        self.stdout.write(self.style.WARNING("Purging existing data..."))
        # Delete in safe dependency order
        OpenEndedToneAnalysis.objects.all().delete()
        QuestionAnalysisCache.objects.all().delete()
        TeamAssessmentAnalysis.objects.all().delete()
        AssessmentResponse.objects.all().delete()
        AssessmentQuestion.objects.all().delete()
        Assessment.objects.all().delete()
        TeamMember.objects.all().delete()
        Team.objects.all().delete()
        CourseMember.objects.all().delete()
        Course.objects.all().delete()
        User.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Purge completed."))