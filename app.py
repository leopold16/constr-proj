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
    Dashboard view to display key metrics, costs, and recent activity.
    """
    with engine.connect() as conn:
        # get summary metrics
        total_projects = conn.execute(text("SELECT COUNT(*) FROM project")).scalar()
        total_employees = conn.execute(text("SELECT COUNT(*) FROM employee")).scalar()
        total_tasks = conn.execute(text("SELECT COUNT(*) FROM task")).scalar()
        total_invoices = conn.execute(text("SELECT COUNT(*) FROM invoice")).scalar()

        # get cost metrics
        costs_summary = conn.execute(
            text("""
                SELECT COUNT(cost_id) AS total_costs, 
                       SUM(cost_amount) AS total_cost_amount
                FROM cost
            """)
        ).fetchone()

        # get recent invoices
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

        # get task statuses
        task_statuses = conn.execute(
            text("""
                SELECT task_status, COUNT(*) AS count
                FROM task
                GROUP BY task_status
            """)
        ).fetchall()
        task_statuses = {row.task_status: row.count for row in task_statuses}

        # get top work orders, sorted by  by cost
        top_work_orders = conn.execute(
            text("""
                SELECT wo.work_order_id, wo.work_order_name, SUM(c.cost_amount) AS total_cost
                FROM billed_to_work_order btwo
                JOIN cost c ON btwo.cost_id = c.cost_id
                JOIN work_order wo ON btwo.work_order_id = wo.work_order_id
                GROUP BY wo.work_order_id, wo.work_order_name
                ORDER BY total_cost DESC
                LIMIT 5
            """)
        ).fetchall()

    return render_template(
        "dashboard.html",
        total_projects=total_projects,
        total_employees=total_employees,
        total_tasks=total_tasks,
        total_invoices=total_invoices,
        costs_summary=costs_summary,
        recent_invoices=recent_invoices,
        task_statuses=task_statuses,
        top_work_orders=top_work_orders,
    )

@app.route("/employee_tasks", methods=["GET", "POST"])
def employee_tasks():
    """
    Manage employee tasks, link tasks to work orders, and display the task-work order relationships.
    """
    message = None

    with engine.connect() as conn:
        if request.method == "POST":
            if "assign_task" in request.form:  # Assign a task to an employee, optionally link it to a work order
                employee_id = request.form.get("employee_id")
                task_name = request.form.get("task_name")
                task_description = request.form.get("task_description", "")
                work_order_id = request.form.get("work_order_id")

                try:
                    # check if the task already exists
                    task = conn.execute(
                        text("SELECT task_id FROM task WHERE task_name = :task_name"),
                        {"task_name": task_name},
                    ).fetchone()

                    if not task:  # create the task if it doesn’t exist
                        task_id = conn.execute(
                            text("""
                                INSERT INTO task (task_name, task_description, task_status)
                                VALUES (:task_name, :task_description, 'Pending') RETURNING task_id
                            """),
                            {"task_name": task_name, "task_description": task_description},
                        ).scalar()
                    else:
                        task_id = task.task_id

                    # assign the task to the employee
                    conn.execute(
                        text("""
                            INSERT INTO employee_assigned_tasks (employee_id, task_id)
                            VALUES (:employee_id, :task_id)
                        """),
                        {"employee_id": employee_id, "task_id": task_id},
                    )

                    # link the task to a work order if given
                    if work_order_id:
                        conn.execute(
                            text("""
                                INSERT INTO task_assigned_work_order (task_id, work_order_id)
                                VALUES (:task_id, :work_order_id)
                            """),
                            {"task_id": task_id, "work_order_id": work_order_id},
                        )

                    conn.commit()
                    message = f"Task '{task_name}' assigned to employee {employee_id} successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error assigning task: {e}"

            elif "update_status" in request.form:  
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

            elif "add_employee" in request.form:  
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

        # get employees and their tasks
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

        # get tasks linked to work orders
        task_work_orders = conn.execute(
            text("""
                SELECT t.task_id, t.task_name, wo.work_order_id, wo.work_order_name
                FROM task t
                LEFT JOIN task_assigned_work_order tawo ON t.task_id = tawo.task_id
                LEFT JOIN work_order wo ON tawo.work_order_id = wo.work_order_id
            """)
        ).fetchall()

        # get work orders to assigne tasks
        work_orders = conn.execute(
            text("SELECT work_order_id, work_order_name FROM work_order")
        ).fetchall()

        # organize task-work order relationships
        task_work_order_dict = {}
        for row in task_work_orders:
            task_work_order_dict[row.task_id] = {
                "work_order_id": row.work_order_id,
                "work_order_name": row.work_order_name,
            }

    return render_template("employee_tasks.html", employees=employees, work_orders=work_orders, task_work_order_dict=task_work_order_dict, message=message)


@app.route("/client_view", methods=["GET", "POST"])
def client_view():
    """
    View clients, their associated projects, and manage the client-project relationship.
    """
    message = None

    with engine.connect() as conn:
        if request.method == "POST":
            if "create_client" in request.form:  
                first_name = request.form.get("client_first_name")
                last_name = request.form.get("client_last_name")
                address = request.form.get("client_address")
                phone = request.form.get("client_phone")
                email = request.form.get("client_email")
                try:
                    conn.execute(
                        text("""
                            INSERT INTO client (client_first_name, client_last_name, client_address, client_phone, client_email)
                            VALUES (:first_name, :last_name, :address, :phone, :email)
                        """),
                        {"first_name": first_name, "last_name": last_name, "address": address, "phone": phone, "email": email}
                    )
                    conn.commit()
                    message = "Client created successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error creating client: {e}"

            elif "assign_project" in request.form:  # to client
                client_id = request.form.get("client_id")
                project_id = request.form.get("project_id")
                try:
                    conn.execute(
                        text("""
                            INSERT INTO client_has_projects (client_id, project_id)
                            VALUES (:client_id, :project_id)
                        """),
                        {"client_id": client_id, "project_id": project_id}
                    )
                    conn.commit()
                    message = f"Project {project_id} assigned to client {client_id} successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error assigning project: {e}"

            elif "unassign_project" in request.form:  # unassign from client
                client_id = request.form.get("client_id")
                project_id = request.form.get("project_id")
                try:
                    conn.execute(
                        text("""
                            DELETE FROM client_has_projects
                            WHERE client_id = :client_id AND project_id = :project_id
                        """),
                        {"client_id": client_id, "project_id": project_id}
                    )
                    conn.commit()
                    message = f"Project {project_id} unassigned from client {client_id} successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error unassigning project: {e}"

        # get all clients
        clients = conn.execute(
            text("""
                SELECT client_id, client_first_name, client_last_name, client_address, client_phone, client_email
                FROM client
            """)
        ).fetchall()

        # get all projects
        projects = conn.execute(
            text("""
                SELECT project_id, project_name
                FROM project
            """)
        ).fetchall()

        # get client-project relationships
        client_projects = conn.execute(
            text("""
                SELECT chp.client_id, p.project_id, p.project_name
                FROM client_has_projects chp
                JOIN project p ON chp.project_id = p.project_id
            """)
        ).fetchall()

        # organize client-project relationships
        client_projects_dict = {}
        for row in client_projects:
            if row.client_id not in client_projects_dict:
                client_projects_dict[row.client_id] = []
            client_projects_dict[row.client_id].append({"project_id": row.project_id, "project_name": row.project_name})

    return render_template("client_view.html", clients=clients, projects=projects, client_projects=client_projects_dict, message=message)

@app.route("/invoice_generator", methods=["GET", "POST"])
def invoice_generator():
    """
    Generate invoices, display invoices linked to specific projects and clients.
    """
    message = None

    with engine.connect() as conn:
        if request.method == "POST":
            if "create_invoice" in request.form: 
                project_id = request.form.get("project_id")
                client_id = request.form.get("client_id")
                issue_date = request.form.get("issue_date")
                due_date = request.form.get("due_date")
                amount = request.form.get("amount")
                try:
                    # insert  new invoice into database
                    invoice_id = conn.execute(
                        text("""
                            INSERT INTO invoice (issue_date, due_date, invoice_amount, invoice_status)
                            VALUES (:issue_date, :due_date, :amount, 'Pending') RETURNING invoice_id
                        """),
                        {"issue_date": issue_date, "due_date": due_date, "amount": amount},
                    ).scalar()

                    # link  invoice to  project
                    if project_id:
                        conn.execute(
                            text("""
                                INSERT INTO invoice_assigned_to_project (invoice_id, project_id)
                                VALUES (:invoice_id, :project_id)
                            """),
                            {"invoice_id": invoice_id, "project_id": project_id},
                        )

                    # link invoice to  client
                    if client_id:
                        conn.execute(
                            text("""
                                INSERT INTO invoice_billed_to (invoice_id, client_id)
                                VALUES (:invoice_id, :client_id)
                            """),
                            {"invoice_id": invoice_id, "client_id": client_id},
                        )

                    conn.commit()
                    message = f"Invoice {invoice_id} created and linked successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error creating invoice: {e}"

        # get all invoices and associated projects and clients
        invoices = conn.execute(
            text("""
                SELECT i.invoice_id, i.issue_date, i.due_date, i.invoice_amount, i.invoice_status,
                       p.project_id, p.project_name,
                       c.client_id, c.client_first_name, c.client_last_name
                FROM invoice i
                LEFT JOIN invoice_assigned_to_project iap ON i.invoice_id = iap.invoice_id
                LEFT JOIN project p ON iap.project_id = p.project_id
                LEFT JOIN invoice_billed_to ibt ON i.invoice_id = ibt.invoice_id
                LEFT JOIN client c ON ibt.client_id = c.client_id
                ORDER BY i.issue_date ASC
            """)
        ).fetchall()

        # get all projects and clients for filter and assign invoices
        projects = conn.execute(
            text("SELECT project_id, project_name FROM project")
        ).fetchall()
        clients = conn.execute(
            text("SELECT client_id, client_first_name, client_last_name FROM client")
        ).fetchall()

    return render_template("invoice_generator.html", invoices=invoices, projects=projects, clients=clients, message=message)

@app.route("/cost_work_order", methods=["GET", "POST"])
def cost_work_order():
    """
    Manage costs and link them to work orders.
    """
    message = None

    with engine.connect() as conn:
        if request.method == "POST":
            if "add_cost" in request.form:  
                cost_description = request.form.get("cost_description")
                cost_amount = request.form.get("cost_amount")
                try:
                    # insert  new cost into database
                    cost_id = conn.execute(
                        text("""
                            INSERT INTO cost (cost_description, cost_amount)
                            VALUES (:cost_description, :cost_amount) RETURNING cost_id
                        """),
                        {"cost_description": cost_description, "cost_amount": cost_amount},
                    ).scalar()
                    conn.commit()
                    message = f"Cost '{cost_description}' added successfully with ID {cost_id}!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error adding cost: {e}"

            elif "link_cost_work_order" in request.form:  # link cost to work order
                cost_id = request.form.get("cost_id")
                work_order_id = request.form.get("work_order_id")
                try:
                    # link cost to work order
                    conn.execute(
                        text("""
                            INSERT INTO billed_to_work_order (cost_id, work_order_id)
                            VALUES (:cost_id, :work_order_id)
                        """),
                        {"cost_id": cost_id, "work_order_id": work_order_id},
                    )
                    conn.commit()
                    message = f"Cost {cost_id} linked to work order {work_order_id} successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error linking cost to work order: {e}"

        # get all costs and associated work orders
        costs_work_orders = conn.execute(
            text("""
                SELECT c.cost_id, c.cost_description, c.cost_amount,
                       wo.work_order_id, wo.work_order_name
                FROM cost c
                LEFT JOIN billed_to_work_order btwo ON c.cost_id = btwo.cost_id
                LEFT JOIN work_order wo ON btwo.work_order_id = wo.work_order_id
                ORDER BY c.cost_id ASC
            """)
        ).fetchall()

        # get all work orders for linking
        work_orders = conn.execute(
            text("SELECT work_order_id, work_order_name FROM work_order")
        ).fetchall()

    return render_template("cost_work_order.html", costs_work_orders=costs_work_orders, work_orders=work_orders, message=message)



@app.route("/project_schedule", methods=["GET", "POST"])
def project_schedule():
    """
    View, filter, add, update, and delete work orders and projects in a single route.
    """
    message = None
    search = request.args.get("search", "")

    with engine.connect() as conn:
        if request.method == "POST":
            if "add_work_order" in request.form:  
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
                    # assign new work order to the project
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

            elif "update_work_order" in request.form:  #
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

            elif "delete_work_order" in request.form:  
                work_order_id = request.form.get("work_order_id")
                try:
                    # delete dependent rows in task_assigned_work_order first
                    conn.execute(
                        text("DELETE FROM task_assigned_work_order WHERE work_order_id = :work_order_id"),
                        {"work_order_id": work_order_id},
                    )

                    # delete dependent rows in assigned_to_project
                    conn.execute(
                        text("DELETE FROM assigned_to_project WHERE work_order_id = :work_order_id"),
                        {"work_order_id": work_order_id},
                    )

                    # delete work order
                    conn.execute(
                        text("DELETE FROM work_order WHERE work_order_id = :work_order_id"),
                        {"work_order_id": work_order_id},
                    )
                    conn.commit()
                    message = f"Work order {work_order_id} and its associations deleted successfully!"
                except Exception as e:
                    conn.rollback()
                    message = f"Error deleting work order: {e}"

            elif "add_project" in request.form:  
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

        # query work orders with filtering and project details
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

        # get project list for adding work orders
        projects = conn.execute(text("SELECT project_id, project_name FROM project")).fetchall()

    return render_template("project_schedule.html", schedule_data=schedule_data, projects=projects, message=message)


if __name__ == "__main__":
    app.run(debug=True)
