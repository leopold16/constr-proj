import os
from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import *
from sqlalchemy.pool import NullPool


app = Flask(__name__, template_folder="templates")

#connect to database
DATABASEURI = "postgresql://lw2999:341647@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)



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
    """
    Display employees and tasks, and assign tasks to employees.
    """
    message = None  # Message to display after assigning a task

    with engine.connect() as conn:
        if request.method == "POST":
            # Get employee and task IDs from the form
            employee_id = int(request.form.get("employee_id"))
            task_id = int(request.form.get("task_id"))

            try:
                # Insert the assignment into the employee_assigned_tasks table
                conn.execute(
                    text("INSERT INTO employee_assigned_tasks (employee_id, task_id) VALUES (:employee_id, :task_id)"),
                    {"employee_id": employee_id, "task_id": task_id}
                )

                # Optionally update the task status in the task table
                conn.execute(
                    text("UPDATE task SET task_status = 'Assigned' WHERE task_id = :task_id"),
                    {"task_id": task_id}
                )

                # Commit the transaction explicitly
                conn.commit()

                message = "Task successfully assigned!"
            except Exception as e:
                # Handle duplicate assignments or other errors
                message = f"Error assigning task: {e}"

        # Fetch all employees
        employees = conn.execute(
            text("SELECT employee_id, employee_name, employee_role FROM employee")
        ).fetchall()
        employees = [
            {"id": row.employee_id, "name": f"{row.employee_name}", "role": row.employee_role}
            for row in employees
        ]

        # Fetch all tasks that are not yet assigned
        tasks = conn.execute(
            text("SELECT task_id, task_name, task_description, task_status FROM task WHERE task_status != 'Completed'")
        ).fetchall()
        tasks = [
            {"id": row.task_id, "name": row.task_name, "description": row.task_description, "status": row.task_status}
            for row in tasks
        ]

        # Fetch task assignments for display
        assignments = conn.execute(
            text("""
                SELECT eat.employee_id, e.employee_name, t.task_name
                FROM employee_assigned_tasks eat
                JOIN employee e ON eat.employee_id = e.employee_id
                JOIN task t ON eat.task_id = t.task_id
            """)
        ).fetchall()
        assignments = [
            {"employee_name": f"{row.employee_name}", "task_name": row.task_name}
            for row in assignments
        ]

    return render_template("employee_tasks.html", employees=employees, tasks=tasks, assignments=assignments, message=message)

@app.route("/client_view", methods=["GET"])
def client_view():
    with engine.connect() as conn:
        # Fetch clients for the dropdown
        clients = conn.execute(
            text("SELECT client_id, CONCAT(client_first_name, ' ', client_last_name) AS client_name FROM lw2999.client")
        ).fetchall()

        # Check if clients exist
        clients_exist = len(clients) > 0

        # Get the selected client_id from the dropdown
        client_id = request.args.get("client_id")
        projects = []
        invoices = []
        work_orders = []
        client_name = None  # Initialize client_name

        if client_id:
            # Fetch the selected client's name
            client_name = conn.execute(
                text("SELECT CONCAT(client_first_name, ' ', client_last_name) AS client_name FROM lw2999.client WHERE client_id = :client_id"),
                {"client_id": client_id},
            ).scalar()

            # Fetch client projects
            projects = conn.execute(
                text("""
                    SELECT p.project_name, p.project_description
                    FROM lw2999.project p
                    JOIN lw2999.client_has_projects chp ON p.project_id = chp.project_id
                    WHERE chp.client_id = :client_id
                """),
                {"client_id": client_id},
            ).fetchall()

            # Fetch client invoices
            invoices = conn.execute(
                text("""
                    SELECT i.invoice_id, i.invoice_amount, i.invoice_status
                    FROM lw2999.invoice i
                    JOIN lw2999.invoice_billed_to ibt ON i.invoice_id = ibt.invoice_id
                    WHERE ibt.client_id = :client_id
                """),
                {"client_id": client_id},
            ).fetchall()

            # Fetch work orders
            work_orders = conn.execute(
                text("""
                    SELECT wo.work_order_name, wo.work_order_status, wo.work_order_start_date, wo.work_order_end_date
                    FROM lw2999.work_order wo
                    JOIN lw2999.assigned_to_project atp ON wo.work_order_id = atp.work_order_id
                    JOIN lw2999.client_has_projects chp ON atp.project_id = chp.project_id
                    WHERE chp.client_id = :client_id
                """),
                {"client_id": client_id},
            ).fetchall()

        # Render the client view template
        return render_template(
            "client_view.html",
            clients=clients,
            projects=projects,
            invoices=invoices,
            work_orders=work_orders,
            clients_exist=clients_exist,
            client_name=client_name,
        )


@app.route("/invoice_generator", methods=["GET", "POST"])
def invoice_generator():
    if request.method == "POST":
        client = request.form.get("client")
        amount = request.form.get("amount")
        invoices.append({"id": len(invoices) + 1, "client": client, "amount": amount, "status": "Pending"})
        return redirect(url_for("invoice_generator"))

    return render_template("invoice_generator.html", invoices=invoices)


@app.route('/project_schedule')
def project_schedule():
    with engine.connect() as conn:
        schedule_data = conn.execute(
            text("""
            SELECT 
                p.project_name,
                wo.work_order_name,
                wo.work_order_status,
                wo.work_order_start_date AS start_date,
                wo.work_order_end_date AS end_date
            FROM lw2999.project p
            JOIN lw2999.assigned_to_project atp ON p.project_id = atp.project_id
            JOIN lw2999.work_order wo ON atp.work_order_id = wo.work_order_id
            WHERE wo.work_order_status != 'Completed'
            ORDER BY wo.work_order_start_date ASC;
            """)
        ).fetchall()
        return render_template('project_schedule.html', schedule_data=schedule_data)



if __name__ == "__main__":
    app.run(debug=True)
