import os
from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import *
from sqlalchemy.pool import NullPool


app = Flask(__name__, template_folder="templates")

#connect to database
#DATABASEURI = "postgresql://lw2999:341647@104.196.222.236/proj1part2"
#engine = create_engine(DATABASEURI)



# Static placeholder data
projects = [
    {"id": 1, "name": "Building A", "status": "In Progress", "progress": 60},
    {"id": 2, "name": "Building B", "status": "Completed", "progress": 100},
]

employees = [
    {"id": 1, "name": "John Doe", "role": "Engineer", "tasks": ["Task A"]},
    {"id": 2, "name": "Jane Smith", "role": "Architect", "tasks": []},
]

tasks = [
    {"id": 1, "name": "Task A", "description": "Foundation Work", "status": "In Progress"},
    {"id": 2, "name": "Task B", "description": "Roof Installation", "status": "Not Started"},
]

invoices = [
    {"id": 1, "client": "Client A", "amount": 5000, "status": "Paid"},
    {"id": 2, "client": "Client B", "amount": 2000, "status": "Pending"},
]

schedule = [
    {"task": "Foundation Work", "employee": "John Doe", "start_date": "2024-11-01", "end_date": "2024-11-10"},
    {"task": "Roof Installation", "employee": "Jane Smith", "start_date": "2024-11-15", "end_date": "2024-11-20"},
]


@app.route("/")
def dashboard():
    return render_template("dashboard.html", projects=projects)


@app.route("/employee_tasks", methods=["GET", "POST"])
def employee_tasks():
    if request.method == "POST":
        task_id = int(request.form.get("task_id"))
        employee_id = int(request.form.get("employee_id"))

        # Assign task to employee
        selected_task = next(task for task in tasks if task["id"] == task_id)
        selected_employee = next(emp for emp in employees if emp["id"] == employee_id)
        selected_employee["tasks"].append(selected_task["name"])
        selected_task["status"] = "Assigned"
        return redirect(url_for("employee_tasks"))

    return render_template("employee_tasks.html", employees=employees, tasks=tasks)


@app.route("/client_view")
def client_view():
    return render_template("client_view.html", projects=projects, invoices=invoices)


@app.route("/invoice_generator", methods=["GET", "POST"])
def invoice_generator():
    if request.method == "POST":
        client = request.form.get("client")
        amount = request.form.get("amount")
        invoices.append({"id": len(invoices) + 1, "client": client, "amount": amount, "status": "Pending"})
        return redirect(url_for("invoice_generator"))

    return render_template("invoice_generator.html", invoices=invoices)


@app.route("/project_schedule")
def project_schedule():
    return render_template("project_schedule.html", schedule=schedule)


if __name__ == "__main__":
    app.run(debug=True)
