import os
from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import *
from sqlalchemy.pool import NullPool


app = Flask(__name__, template_folder="templates")

app.jinja_env.globals.update(zip=zip)


#connect to database
DATABASEURI = "postgresql://lw2999:341647@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)

@app.route("/")
def dashboard():
    """
    Dashboard view to display key metrics and recent activity.
    """
    with engine.connect() as conn:
        # Fetch summary metrics
        total_projects = conn.execute(text("SELECT COUNT(*) FROM project")).scalar()
        total_employees = conn.execute(text("SELECT COUNT(*) FROM employee")).scalar()
        total_tasks = conn.execute(text("SELECT COUNT(*) FROM task")).scalar()
        total_invoices = conn.execute(text("SELECT COUNT(*) FROM invoice")).scalar()

        # Fetch recent invoices (limit to 5)
        recent_invoices = conn.execute(
            text("""
                SELECT i.invoice_id, i.invoice_amount, i.invoice_status, i.due_date,
                       c.client_first_name, c.client_last_name
                FROM invoice i
                LEFT JOIN invoice_billed_to ibt ON i.invoice_id = ibt.invoice_id
                LEFT JOIN client c ON ibt.client_id = c.client_id
                ORDER BY i.due_date DESC
                LIMIT 5
            """)
        ).fetchall()
        recent_invoices = [
            {
                "id": row.invoice_id,
                "amount": row.invoice_amount,
                "status": row.invoice_status,
                "due_date": row.due_date,
                "client": f"{row.client_first_name} {row.client_last_name}" if row.client_first_name else "N/A",
            }
            for row in recent_invoices
        ]

        # Fetch task statuses
        task_statuses = conn.execute(
            text("""
                SELECT task_status, COUNT(*) AS count
                FROM task
                GROUP BY task_status
            """)
        ).fetchall()
        task_statuses = {row.task_status: row.count for row in task_statuses}

    return render_template(
        "dashboard.html",
        total_projects=total_projects,
        total_employees=total_employees,
        total_tasks=total_tasks,
        total_invoices=total_invoices,
        recent_invoices=recent_invoices,
        task_statuses=task_statuses,
    )

@app.route("/employee_tasks", methods=["GET", "POST"])
def employee_tasks():
    """
    View employee tasks, assign tasks by typing task names, create new employees,
    and update task statuses.
    """
    message = None

    with engine.connect() as conn:
        if request.method == "POST":
            if "assign_task" in request.form:  # Assign a task to an employee
                employee_id = request.form.get("employee_id")
                task_name = request.form.get("task_name")
                task_description = request.form.get("task_description", "")

                try:
                    # Check if the task already exists
                    task = conn.execute(
                        text("SELECT task_id FROM task WHERE task_name = :task_name"),
                        {"task_name": task_name},
                    ).fetchone()

                    if not task:  # Create the task if it doesn’t exist
                        task_id = conn.execute(
                            text("""
                                INSERT INTO task (task_name, task_description, task_status)
                                VALUES (:task_name, :task_description, 'Pending') RETURNING task_id
                            """),
                            {"task_name": task_name, "task_description": task_description},
                        ).scalar()
                    else:
                        task_id = task.task_id

                    # Assign the task to the employee
                    conn.execute(
                        text("""
                            INSERT INTO employee_assigned_tasks (employee_id, task_id)
                            VALUES (:employee_id, :task_id)
                        """),
                        {"employee_id": employee_id, "task_id": task_id},
                    )
                    conn.commit()
                    message = f"Task '{task_name}' assigned to employee {employee_id} successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error assigning task: {e}"

            elif "update_status" in request.form:  # Update task status
                task_id = request.form.get("task_id")
                new_status = request.form.get("new_status")

                try:
                    conn.execute(
                        text("UPDATE task SET task_status = :new_status WHERE task_id = :task_id"),
                        {"new_status": new_status, "task_id": task_id},
                    )
                    conn.commit()
                    message = f"Task {task_id} status updated successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error updating task status: {e}"

            elif "add_employee" in request.form:  # Add a new employee
                employee_name = request.form.get("employee_name")
                role = request.form.get("role")

                try:
                    conn.execute(
                        text("""
                            INSERT INTO employee (employee_name, employee_role)
                            VALUES (:employee_name, :role)
                        """),
                        {"employee_name": employee_name, "role": role},
                    )
                    conn.commit()
                    message = f"New employee '{employee_name}' added successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error adding employee: {e}"

        # Fetch employees and their tasks with descriptions and statuses
        employees = conn.execute(
            text("""
                SELECT e.employee_id, e.employee_name, e.employee_role,
                       ARRAY_AGG(t.task_id) AS task_ids,
                       ARRAY_AGG(t.task_name) AS task_names,
                       ARRAY_AGG(t.task_description) AS descriptions,
                       ARRAY_AGG(t.task_status) AS statuses
                FROM employee e
                LEFT JOIN employee_assigned_tasks eat ON e.employee_id = eat.employee_id
                LEFT JOIN task t ON eat.task_id = t.task_id
                GROUP BY e.employee_id, e.employee_name, e.employee_role
            """)
        ).fetchall()

    return render_template("employee_tasks.html", employees=employees, message=message)

@app.route("/client_view", methods=["GET", "POST"])
def client_view():
    """
    View all clients, add a new client, and delete existing clients.
    """
    message = None  # Feedback message for the user

    with engine.connect() as conn:
        if request.method == "POST":
            if "create_client" in request.form:  # Handle new client creation
                first_name = request.form.get("client_first_name")
                last_name = request.form.get("client_last_name")
                address = request.form.get("client_address")
                phone = request.form.get("client_phone")
                email = request.form.get("client_email")

                try:
                    # Insert the new client into the database
                    conn.execute(
                        text("""
                            INSERT INTO client (client_first_name, client_last_name, client_address, client_phone, client_email)
                            VALUES (:first_name, :last_name, :address, :phone, :email)
                        """),
                        {
                            "first_name": first_name,
                            "last_name": last_name,
                            "address": address,
                            "phone": phone,
                            "email": email,
                        }
                    )
                    conn.commit()
                    message = "New client created successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error creating client: {e}"

            elif "delete_client" in request.form:  # Handle client deletion
                client_id = int(request.form.get("client_id"))
                try:
                    # Delete the client and cascade delete related data
                    conn.execute(
                        text("DELETE FROM client WHERE client_id = :client_id"),
                        {"client_id": client_id}
                    )
                    conn.commit()
                    message = f"Client {client_id} and related data deleted successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error deleting client: {e}"

        # Fetch all clients for display
        clients = conn.execute(
            text("""
                SELECT client_id, client_first_name, client_last_name, client_address, client_phone, client_email
                FROM client
            """)
        ).fetchall()

        # Convert client data into a list of dictionaries
        clients = [
            {
                "id": row.client_id,
                "first_name": row.client_first_name,
                "last_name": row.client_last_name,
                "address": row.client_address,
                "phone": row.client_phone,
                "email": row.client_email,
            }
            for row in clients
        ]

    return render_template("client_view.html", clients=clients, message=message)


@app.route("/invoice_generator", methods=["GET", "POST"])
def invoice_generator():
    """
    Generate and display invoices with client associations.
    """
    message = None

    with engine.connect() as conn:
        if request.method == "POST":
            if "create_invoice" in request.form:
                # Get invoice details from the form
                client_id = int(request.form.get("client_id"))
                invoice_amount = float(request.form.get("invoice_amount"))
                issue_date = request.form.get("issue_date")
                due_date = request.form.get("due_date")

                try:
                    # Insert invoice into the invoice table
                    conn.execute(
                        text("""
                            INSERT INTO invoice (issue_date, due_date, invoice_amount, invoice_status)
                            VALUES (:issue_date, :due_date, :invoice_amount, 'Pending')
                        """),
                        {
                            "issue_date": issue_date,
                            "due_date": due_date,
                            "invoice_amount": invoice_amount,
                        }
                    )

                    # Get the ID of the last inserted invoice
                    result = conn.execute(text("SELECT LASTVAL()"))
                    invoice_id = result.fetchone()[0]

                    # Link the invoice to the client in the invoice_billed_to table
                    conn.execute(
                        text("""
                            INSERT INTO invoice_billed_to (invoice_id, client_id)
                            VALUES (:invoice_id, :client_id)
                        """),
                        {
                            "invoice_id": invoice_id,
                            "client_id": client_id,
                        }
                    )

                    conn.commit()
                    message = "Invoice created successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error creating invoice: {e}"

            elif "mark_paid" in request.form:
                # Mark an invoice as paid
                invoice_id = int(request.form.get("invoice_id"))
                try:
                    conn.execute(
                        text("UPDATE invoice SET invoice_status = 'Paid' WHERE invoice_id = :invoice_id"),
                        {"invoice_id": invoice_id}
                    )
                    conn.commit()
                    message = "Invoice marked as paid!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error updating invoice: {e}"

        # Fetch clients for dropdown
        clients = conn.execute(
            text("SELECT client_id, client_first_name, client_last_name FROM client")
        ).fetchall()
        clients = [{"id": row.client_id, "name": f"{row.client_first_name} {row.client_last_name}"} for row in clients]

        # Fetch all invoices with client information
        invoices = conn.execute(
            text("""
                SELECT i.invoice_id, i.invoice_amount, i.issue_date, i.due_date, i.invoice_status, 
                       c.client_first_name, c.client_last_name
                FROM invoice i
                LEFT JOIN invoice_billed_to ibt ON i.invoice_id = ibt.invoice_id
                LEFT JOIN client c ON ibt.client_id = c.client_id
            """)
        ).fetchall()
        invoices = [
            {
                "id": row.invoice_id,
                "amount": row.invoice_amount,
                "issue_date": row.issue_date,
                "due_date": row.due_date,
                "status": row.invoice_status,
                "client": f"{row.client_first_name} {row.client_last_name}" if row.client_first_name else "N/A",
            }
            for row in invoices
        ]

    return render_template("invoice_generator.html", clients=clients, invoices=invoices, message=message)

@app.route("/project_schedule", methods=["GET", "POST"])
def project_schedule():
    """
    View, filter, add, update, and delete work orders and projects in a single route.
    """
    message = None
    search = request.args.get("search", "")

    with engine.connect() as conn:
        if request.method == "POST":
            if "add_work_order" in request.form:  # Adding a new work order
                project_id = request.form.get("project_id")
                work_order_name = request.form.get("work_order_name")
                work_order_status = request.form.get("work_order_status")
                start_date = request.form.get("start_date")
                end_date = request.form.get("end_date")
                try:
                    conn.execute(
                        text("""
                            INSERT INTO work_order (work_order_name, work_order_status, work_order_start_date, work_order_end_date)
                            VALUES (:work_order_name, :work_order_status, :start_date, :end_date)
                        """),
                        {
                            "work_order_name": work_order_name,
                            "work_order_status": work_order_status,
                            "start_date": start_date,
                            "end_date": end_date,
                        },
                    )
                    # Assign the new work order to the project
                    work_order_id = conn.execute(text("SELECT MAX(work_order_id) FROM work_order")).scalar()
                    conn.execute(
                        text("""
                            INSERT INTO assigned_to_project (project_id, work_order_id)
                            VALUES (:project_id, :work_order_id)
                        """),
                        {"project_id": project_id, "work_order_id": work_order_id},
                    )
                    conn.commit()
                    message = "Work order added successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error adding work order: {e}"

            elif "update_work_order" in request.form:  # Updating a work order status
                work_order_id = request.form.get("work_order_id")
                new_status = request.form.get("new_status")
                try:
                    conn.execute(
                        text("UPDATE work_order SET work_order_status = :new_status WHERE work_order_id = :work_order_id"),
                        {"new_status": new_status, "work_order_id": work_order_id},
                    )
                    conn.commit()
                    message = f"Work order {work_order_id} updated successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error updating work order: {e}"

            elif "delete_work_order" in request.form:  # Deleting a work order
                work_order_id = request.form.get("work_order_id")
                try:
                    # Delete dependent rows in task_assigned_work_order first
                    conn.execute(
                        text("DELETE FROM task_assigned_work_order WHERE work_order_id = :work_order_id"),
                        {"work_order_id": work_order_id},
                    )

                    # Delete dependent rows in assigned_to_project
                    conn.execute(
                        text("DELETE FROM assigned_to_project WHERE work_order_id = :work_order_id"),
                        {"work_order_id": work_order_id},
                    )

                    # Delete the work order
                    conn.execute(
                        text("DELETE FROM work_order WHERE work_order_id = :work_order_id"),
                        {"work_order_id": work_order_id},
                    )
                    conn.commit()
                    message = f"Work order {work_order_id} and its associations deleted successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error deleting work order: {e}"

            elif "add_project" in request.form:  # Adding a new project
                project_name = request.form.get("project_name")
                project_description = request.form.get("project_description")
                try:
                    conn.execute(
                        text("""
                            INSERT INTO project (project_name, project_description)
                            VALUES (:project_name, :project_description)
                        """),
                        {
                            "project_name": project_name,
                            "project_description": project_description,
                        },
                    )
                    conn.commit()
                    message = "Project created successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error creating project: {e}"

        # Query work orders with filtering and project details
        query = """
            SELECT 
                p.project_name,
                p.project_description,
                wo.work_order_id,
                wo.work_order_name,
                wo.work_order_status,
                wo.work_order_start_date AS start_date,
                wo.work_order_end_date AS end_date
            FROM project p
            JOIN assigned_to_project atp ON p.project_id = atp.project_id
            JOIN work_order wo ON atp.work_order_id = wo.work_order_id
        """
        if search:
            query += " WHERE p.project_name ILIKE :search OR wo.work_order_name ILIKE :search"
        query += " ORDER BY wo.work_order_start_date ASC"

        schedule_data = conn.execute(text(query), {"search": f"%{search}%"} if search else {}).fetchall()

        # Fetch project list for adding work orders
        projects = conn.execute(text("SELECT project_id, project_name FROM project")).fetchall()

    return render_template("project_schedule.html", schedule_data=schedule_data, projects=projects, message=message)


if __name__ == "__main__":
    app.run(debug=True)
