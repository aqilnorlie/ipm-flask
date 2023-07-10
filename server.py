# flask --app server run --debug

from flask import Flask, render_template, session, redirect, url_for, request, send_file, make_response
import os, json, datetime, io, base64, mimetypes, oracledb, hashlib

oracledb.init_oracle_client(
    lib_dir=r"C:\instantclient_21_10"
)  # install oracle client and set variable
con = oracledb.connect(
    user=os.environ.get("oracle_user"),
    password=os.environ.get("oracle_pass"),
    dsn=os.environ.get("oracle_dns"),
    port=os.environ.get("oracle_port"),
)

# CHECK CONNECTION
if con.is_healthy() == True:
    print("SUCCESSFULLY CONNECTED TO DB.")
else:
    print("ERROR CONNECTING TO DB.")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("secret_key")  # set your own secret key

# ================================================================================================================================
# ================================================================================================================================

@app.route("/", methods=["GET", "POST"])
def login():
    if "email" in session:
        return redirect(url_for("project_list"))

    if request.method == "POST":
        email = request.form["email"]  # get data from email input
        password = request.form["password"]  # get data from password input
        password_hash = hashlib.md5(password.encode()).hexdigest()
        cur = con.cursor()
        user_info = cur.execute(
            "SELECT id, first_name, last_name, email FROM ipm_user WHERE email = :1 AND password = :2",
            (email, password_hash),
        )
        if user_info:
            detail = user_info.fetchall()
            for id, fname, lname, email in detail:
                session["fname"] = fname  # insert name into session
                session["lname"] = lname
                session["email"] = email
                session["user_id"] = id
                return redirect(url_for("project_list"))

    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "email" in session:
        # session.clear()

        print("currently at dashboard page")
        cur = con.cursor()

        cur.execute("""
        select p.id, u.first_name, p.name from ipm_user u join ipm_project_team t on u.id = t.user_id join
        ipm_project_team_junction j on t.id = j.project_team_id join ipm_project p on
        p.id = j.project_id where u.id = :1 """,(session["user_id"],)
        )
        columns = [col[0] for col in cur.description]
        cur.rowfactory = lambda *args: dict(zip(columns, args))
        data1 = cur.fetchall()

        cur.execute("SELECT * from ipm_user")
        columns = [col[0] for col in cur.description]
        cur.rowfactory = lambda *args: dict(zip(columns, args))
        data2 = cur.fetchall()

        cur.execute("SELECT * from ipm_ref_duration")
        columns = [col[0] for col in cur.description]
        cur.rowfactory = lambda *args: dict(zip(columns, args))
        data3 = cur.fetchall()

        if request.method == "POST":
            if request.form["d_action"] == "data_save":

                form_data = request.form["form_data"]
                insert_data = json.loads(form_data)

                pname = insert_data["name"]
                pdesc = insert_data["desc"]
                psdate = insert_data["start"]
                pedate = insert_data["end"]
                pmanager = insert_data["manager"]

                cur.execute(
                    """
                    INSERT INTO ipm_project 
                    (id, name, description, planned_start_date, planned_end_date, note, project_id_custom)
                    VALUES
                    (IPM_PROJECT_SEQ.nextval, :2, :3, TO_DATE(:4,'fxYYYY-MM-DD'), TO_DATE(:5,'fxYYYY-MM-DD'), :8, CONCAT('p', IPM_PROJECT_SEQ.currval))
                    """,
                    (pname, pdesc, psdate, pedate, pdesc)
                )

                cur.execute(
                    """
                    INSERT INTO ipm_project_team
                    (id, team_id, user_id)
                    VALUES
                    (IPM_PROJECT_TEAM_SEQ.nextval, :2, :3)
                    """,
                    (None, pmanager)
                )

                cur.execute(
                    """
                    INSERT INTO ipm_project_team_junction
                    (id, project_team_id, project_id)
                    VALUES
                    (IPM_PROJECT_TEAM_JUNCTION_SEQ.nextval, IPM_PROJECT_TEAM_SEQ.currval, IPM_PROJECT_SEQ.currval)
                    """
                )

                ptype = insert_data["ptype"]

                if ptype == "public":
                    req2join = insert_data["requestToJoin"]
                    if req2join == True:
                        req2join = 1 # 1 = user has to request to join
                    else:
                        req2join = 0 # 0 = user does not have to request

                    cur.execute(
                        """
                        INSERT INTO ipm_project_public
                        (project_id, request_to_join)
                        VALUES
                        (IPM_PROJECT_SEQ.currval, :request_to_join)
                        """,
                        request_to_join = req2join
                    )
                elif ptype == "private":
                    project_pw_hash = hashlib.md5(insert_data["privateProPW"].encode()).hexdigest()
                    cur.execute(
                        """
                        INSERT INTO ipm_project_private
                        (project_id, password)
                        VALUES
                        (IPM_PROJECT_SEQ.currval, :password)
                        """,
                        password = project_pw_hash
                    )

                con.commit()

                return (
                    json.dumps({"data": "sucess"}), 
                    200,
                    {"ContentType": "application/json"},
                )  # send back through AJAX (SUCESS)

            if request.form["d_action"] == "update_page":
                project_id = request.form["project"]
                
                # START: DISPLAY PROJECT MANAGER
                cur.execute(
                    """
                    select * from ipm_project_team_junction j 
                    join ipm_project_team pt on j.project_team_id = pt.id 
                    join ipm_user u on u.id = pt.user_id 
                    where j.project_id = :1 and pt.team_id is null
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                
                user_info = cur.fetchall()
                # END: DISPLAY PROJECT MANAGER

                # list of employees for modal PROJECT MANAGER
                cur.execute("select id, first_name, last_name from ipm_user")
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_user = cur.fetchall()

                # for SCOPE in modal ADD SPECIFICATION

                cur.execute(
                    """
                    SELECT id, name from ipm_scope 
                    where id IN 
                        (SELECT sc.id FROM ipm_scope sc 
                        join ipm_project p on p.id = sc.project_id
                        where p.id = :1)
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                
                projectScope = cur.fetchall()
                
                # for EMPLOYEE in modal ADD SPECIFICATION

                cur.execute(
                    """
                    SELECT e.first_name || ' ' || e.last_name as full_name, e.id
                    FROM ipm_user e
                    JOIN ipm_project_team t ON e.id = t.user_id
                    JOIN ipm_project_team_junction j ON j.project_team_id = t.id
                    WHERE j.project_id = :1
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                
                teamMember = cur.fetchall()

                # START: data for OVERALL PROJECT TREEVIEW
                
                cur.execute(
                    """
                    Select project_id_custom, name 
                    from ipm_project 
                    where id = :1
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                
                current_project = cur.fetchall()

                cur.execute(
                    """
                    Select sc.name, sc.id, sc.scope_id_custom, p.project_id_custom 
                    from ipm_scope sc 
                    join ipm_project p on sc.project_id = p.id 
                    where sc.project_id = :1
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                
                current_scope = cur.fetchall()

                cur.execute(
                    """
                    select sp.id, sp.name, sp.spec_id_custom, sc.scope_id_custom 
                    from ipm_specification sp 
                    join ipm_scope sc on sc.id = sp.scope_id
                    join ipm_project p on p.id = sc.project_id 
                    where p.id = :1
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                
                current_spec = cur.fetchall()

                # END: data for OVERALL PROJECT TREEVIEW

                # START: data for PROJECT FOLDER TREEVIEW
                
                # FILE CATEGORY
                cur.execute("select * from ipm_file_category where project_id = :1",(project_id,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                fileCategoryAll = cur.fetchall()
                
                # FILES
                cur.execute("select id, file_name, file_id_custom, file_category_id from ipm_project_file where project_id = :1",(project_id,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                fileList = cur.fetchall()

                for f in fileList:
                    # f['FILE_'] = base64.b64encode(f['FILE_'].read()).decode('utf-8')
                    fileName = str(f["FILE_NAME"]).lower()
                    if fileName.endswith(('.png', '.jpg', '.jpeg')):
                        f["icon"] = "fa-regular fa-file-image"
                    elif fileName.endswith('.txt'):
                        f["icon"] = "fa-regular fa-file-lines"
                    elif fileName.endswith('.pdf'):
                        f["icon"] = "fa-regular fa-file-pdf"
                    elif fileName.endswith('.docx'):
                        f["icon"] = "fa-regular fa-file-word"
                    else:
                        f["icon"] = "fa-regular fa-file"
            
                # END: data for PROJECT FOLDER TREEVIEW

                # START: data for all team member

                cur.execute(
                    """
                    select * from ipm_user u 
                    join ipm_project_team t on u.id = t.user_id 
                    join ipm_project_team_junction j on j.project_team_id = t.id 
                    where j.project_id = :1
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_member = cur.fetchall()

                # END: data for all team member

                # START : data for all specification table
                
                cur.execute(
                     """
                    SELECT s.id,s.name spec_name, s.percentage,s.scope_id, c.name scope_name, u.first_name || ' ' || u.last_name as full_name,
                    d.name duration, st.name status
                    FROM ipm_specification s
                    JOIN ipm_scope c ON s.scope_id = c.id
                    JOIN ipm_project p on p.id = c.project_id
                    JOIN ipm_user u ON u.id = s.assigned_user_id
                    JOIN ipm_ref_status st ON st.id = s.status_id
                    JOIN ipm_ref_duration d ON d.id = s.duration_id
                    WHERE p.id = :1
                    """,(project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_spec = cur.fetchall()
                # END : data for all specification table

                # START : data for simple bar chart
                dataForBarArr = []
                cur.execute(
                    """
                    SELECT * FROM ipm_project where id = :1
                    """,(project_id,)
                )

                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                data_project_bar = cur.fetchall()

                cur.execute("SELECT * from ipm_scope")
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                scope_all = cur.fetchall()

                for i in data_project_bar:
                    projectId = i.get("ID")
                    dataForBarMap = {}
                    dataForBarMap["project_id"] = i.get("ID") 
                    dataForBarMap["project_name"] = i.get("NAME")
                    totalPercentageScopeMap = {}
                    totalPercentagePerProject = 0.00
                    countScope = 0
                    for b in scope_all:
                        if b.get("PROJECT_ID") == projectId:
                            scopeId = b.get("ID")
                            totalPercentagePerScope = 0.00
                            countScope += 1
                            countSpec = 0
                            for c in all_spec:
                                if c.get("SCOPE_ID") == scopeId:
                                    totalPercentagePerScope += float(c.get("PERCENTAGE"))
                                    countSpec += 1
                            if countSpec != 0:
                                divSpec = totalPercentagePerScope / (countSpec * 100)
                                multipliedSpec = '{:.2f}'.format(divSpec * 100)
                                totalPercentageScopeMap[b.get("NAME")] = multipliedSpec
                                totalPercentagePerProject += float(multipliedSpec)
                            else:
                                totalPercentageScopeMap[b.get("NAME")] = '{:.2f}'.format(0.00)
                    if countScope != 0:
                        divPro = totalPercentagePerProject / (countScope * 100)
                        multipliedPro = '{:.2f}'.format(divPro * 100)
                        dataForBarMap["total_percentage"] =  multipliedPro
                        dataForBarMap["scope_percentage"] = totalPercentageScopeMap
                        dataForBarArr.append(dataForBarMap)
                    else:
                        dataForBarMap["total_percentage"] =  '{:.2f}'.format(0.00)
                        dataForBarMap["scope_percentage"] =  totalPercentageScopeMap
                        dataForBarArr.append(dataForBarMap)
                    # END : data for simple bar chart

                # START - RIGHT SIDE 
                # to get id employee and name based on project id 
                cur.execute(
                    """
                    SELECT DISTINCT e.first_name || ' ' || e.last_name as full_name , e.id from ipm_project_team_junction p join ipm_project_team 
                    s on s.id = p.project_team_id join ipm_user e on e.id = s.user_id where s.team_id IS not NULL and p.project_id = :1
                    """, (project_id,)
                )

                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                get_team = cur.fetchall()
                
                # get all member with manager
                cur.execute(
                    """
                    select DISTINCT e.first_name || ' ' || e.last_name as full_name, e.id from ipm_project_team_junction p join ipm_project_team 
                    s on s.id = p.project_team_id join ipm_user e on e.id = s.user_id where p.project_id = :1
                    """, (project_id,)
                )

                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_team = cur.fetchall()

                cur.execute(
                    """
                    select sp.id,sp.name,sp.description,sp.added_date,sp.percentage,sp.spec_id_custom,sp.scope_id,sp.status_id,
                    sp.duration_id,sp.assigned_user_id from ipm_specification sp 
                    join ipm_scope s on sp.scope_id = s.id where s.project_id = :1

                    """, (project_id,)
                )

                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                specListProject = cur.fetchall()
            
                list_task = []
                name_task = {}
                for e in all_team:
                    if specListProject:
                        for i in specListProject:
                            if i.get("ASSIGNED_USER_ID") == e.get("ID"):
                                name_id = e.get("FULL_NAME") + "_" + str(e.get("ID"))
                                list_task.append(i.get("NAME")) 
                                name_task[name_id] = list_task
                            else:
                                name_id = e.get("FULL_NAME") + "_" + str(e.get("ID"))
                                name_task[name_id] = list_task
                
                    else:
                        name_id = e.get("FULL_NAME") + "_" + str(e.get("ID"))
                        name_task[name_id] = list_task
                    list_task = []

                dict_data = {}
                for e in all_team:
                    dict_data[e.get("FULL_NAME")] = {}
                    for i in specListProject:
                        dict_data[e.get("FULL_NAME")][i.get("NAME")] = 0
                        if i.get("ASSIGNED_USER_ID") == e.get("ID"):
                            dict_data[e.get("FULL_NAME")][i.get("NAME")] = i.get("PERCENTAGE")
                
                dict_test = {}
                for i in specListProject:
                    dict_test[i.get("NAME")] = {}
                    for e in all_team:
                        dict_test[i.get("NAME")][e.get("FULL_NAME")] = 0
                        if i.get("ASSIGNED_USER_ID") == e.get("ID"):
                            dict_test[i.get("NAME")][e.get("FULL_NAME")] = i.get("PERCENTAGE")
                
                # END - RIGHT SIDE

                return (
                    json.dumps({
                        "data": "sucess",
                        "project_manager": user_info,
                        "all_user": all_user,
                        "projectScope": projectScope,
                        "teamMember": teamMember,
                        "current_project": current_project,
                        "current_scope": current_scope,
                        "current_spec": current_spec,
                        "fileCategoryAll": fileCategoryAll,
                        "fileList": fileList,
                        "allMember": all_member,
                        "all_spec" : all_spec,
                        "dataForBar" : dataForBarArr,
                        "dict_data" : dict_data,
                        "dict_test" : dict_test
                        
                    }), 
                    200,
                    {"ContentType": "application/json"},
                )
                

            if request.form["d_action"] == "delete_project_manager":
                manager_team_id = request.form["managerTId"]
                project_id = request.form["projectIdEditManager"]
                manager_user_id = request.form["managerUserId"]

                # delete_statements = [
                #     ("""
                #     delete from ipm_project_team where id = :1
                #     """,
                #     (manager_team_id,)),
                #     ("""
                #     delete from ipm_project_team_junction where project_team_id = :1
                #     """,
                #     (manager_team_id,)),
                #     ("""
                #     delete from ipm_specification sp 
                #     where sp.id IN 
                #         (SELECT sp.id FROM ipm_specification sp 
                #         join ipm_scope sc on sc.id = sp.scope_id 
                #         join ipm_project p on p.id = sc.project_id
                #         where p.id = :1 and assigned_user_id = :2)
                #     """,
                #     (project_id, manager_user_id,))
                # ]

                # cur.executemany(*delete_statements)

                # delete manager in ipm_project_team
                # delete manager in ipm_project_team_junction
                # delete manager's spec.

                cur.execute("delete from ipm_project_team_junction where project_team_id = :1",(manager_team_id,))
                cur.execute("delete from ipm_project_team where id = :1",(manager_team_id,))
                cur.execute("""
                    delete from ipm_specification sp 
                    where sp.id IN 
                        (SELECT sp.id FROM ipm_specification sp 
                        join ipm_scope sc on sc.id = sp.scope_id 
                        join ipm_project p on p.id = sc.project_id
                        where p.id = :1 and assigned_user_id = :2)
                    """,
                    (project_id, manager_user_id,)
                )

                # set member team_id to 0 to cater for after when manager is deleted
                cur.execute("select * from view_ipm_project_team where project_id = :1",(project_id,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                team_member_row = cur.fetchall()

                for row in team_member_row:
                    cur.execute("""
                        UPDATE ipm_project_team
                        SET team_id = 0
                        WHERE ID = :1
                        """, (row["IPM_PROJECT_TEAM_ID"],)
                    )
                    con.commit()

                con.commit()

                return render_template(
                    "index.html", name=session["fname"], projects=data1, users=data2, all_duration=data3
                )

            if request.form["d_action"] == "update_project_manager":
                print("update project manager")

                chosen_manager_emp_id = request.form.get("empList")
                manager_team_id = request.form["managerTId"]
                project_id = request.form["projectIdEditManager"]
                manager_user_id = request.form["managerUserId"]
                
                cur.execute("select * from view_ipm_project_team where project_id = :1",(project_id,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                existingMember = cur.fetchall()

                existingMemberList = []
                existingMemberEmpIdList = []
                for a in existingMember:
                    existingMemberList.append(a)
                    existingMemberEmpIdList.append(int(a["USER_ID"]))
                
                prom_team = cur.execute("select * from ipm_project_team where id = :1",(manager_team_id,)).fetchone()

                # project has a manager (CHANGE manager)

                if manager_team_id:
                    
                    # check if user actually changes the manager when clicking the update button. If not, do nothing and go back to the page.
                    if int(prom_team[2]) != int(chosen_manager_emp_id):
                        
                        # START: EXISTING member becomes manager (existing member will replace the current existing manager)
                        
                        managerPromProjectId = 0
                        for a in existingMemberList:
                            
                            if int(chosen_manager_emp_id) == int(a["USER_ID"]):
                                # NEW manager
                                empRow = cur.execute("select * from ipm_project_team where id = :1",(a["IPM_PROJECT_TEAM_ID"],)).fetchone()
                                newManagerEmpId = empRow[2]
                                # OLD manager
                                managerRow = cur.execute("select * from ipm_project_team where id = :1",(manager_team_id,)).fetchone()
                                oldManagerEmpId = managerRow[2]

                                # swap the emp_id between the NEW and OLD manager row
                                cur.execute("UPDATE ipm_project_team SET user_id = :1 WHERE ID = :2",(oldManagerEmpId,empRow[0]))
                                cur.execute("UPDATE ipm_project_team SET user_id = :1 WHERE ID = :2",(newManagerEmpId,managerRow[0]))
                                con.commit()
                                
                                managerPromProjectId = a["IPM_PROJECT_TEAM_ID"]
                                break
                                
                        # END: EXISTING member becomes manager (existing member will replace the current existing manager)
                        
                        # START: NEW member becomes manager (new member will replace the current existing manager)
                            
                        # new member becomes the manager (will be added into the project team) and the old manager will be a member.

                        if int(chosen_manager_emp_id) not in existingMemberEmpIdList:

                            # create new row in prom_project_team for old manager as member

                            cur.execute(
                                """
                                INSERT INTO ipm_project_team
                                (id, team_id, user_id)
                                VALUES
                                (IPM_PROJECT_TEAM_SEQ.nextval, :1, :2)
                                """,
                                (manager_team_id,prom_team[2])
                            )
                            con.commit()
                            
                            cur.execute(
                                """
                                INSERT INTO ipm_project_team_junction
                                (id, project_team_id, project_id)
                                VALUES
                                (IPM_PROJECT_TEAM_JUNCTION_SEQ.nextval, IPM_PROJECT_TEAM_SEQ.currval, :1)
                                """,
                                (project_id,)
                            )
                            con.commit()
                            
                            # set new manager in row of the old manager
                            cur.execute("UPDATE ipm_project_team SET user_id = :1 WHERE ID = :2",(chosen_manager_emp_id,prom_team[0]))
                            con.commit()

                            managerPromProjectId = prom_team[0]
                            
                            con.commit()
                        
                        # END: NEW member becomes manager (new member will replace the current existing manager)
                        
                        # update team_id for members
                        cur.execute("select * from view_ipm_project_team where project_id = :1 and team_id is not null",(project_id,))
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        existingMemberUpdated = cur.fetchall()

                        for c in existingMemberUpdated:
                            rowUpdatedRow = cur.execute("select * from ipm_project_team where id = :1",(c["IPM_PROJECT_TEAM_ID"],)).fetchone()
                            rowUpdatedId = rowUpdatedRow[0]
                            cur.execute("UPDATE ipm_project_team SET team_id = :1 WHERE ID = :2",(prom_team[0],rowUpdatedId))
                            con.commit()
                                
                    # user just click the update button without changing the manager 
                    else:
                        return render_template(
                            "index.html", name=session["fname"], projects=data1, users=data2, all_duration=data3
                        )
                    
                    return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)
                        
                # project does not have a manager (ADD project manager)

                else:
                    
                    # START: set an EXISTING member to be the manager
                    
                    if int(chosen_manager_emp_id) in existingMemberEmpIdList:
                        print("existing member jdi PM")

                        cur.execute(
                            """
                            INSERT INTO ipm_project_team
                            (id, team_id, user_id)
                            VALUES
                            (IPM_PROJECT_TEAM_SEQ.nextval, :1, :2)
                            """,
                            (None,chosen_manager_emp_id,)
                        )
                        con.commit()
                        
                        cur.execute(
                            """
                            INSERT INTO ipm_project_team_junction
                            (id, project_team_id, project_id)
                            VALUES
                            (IPM_PROJECT_TEAM_JUNCTION_SEQ.nextval, IPM_PROJECT_TEAM_SEQ.currval, :1)
                            """,
                            (project_id,)
                        )
                        con.commit()

                        cur.execute("select * from view_ipm_project_team where project_id = :1 and team_id is not null",(project_id,))
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        existingMemberUpdated = cur.fetchall()

                        for e in existingMemberUpdated:
                            # delete duplicate row of old existing member that has been selected to become the new manager
                            if ((int(e["USER_ID"]) == int(chosen_manager_emp_id)) and "TEAM_ID" in e):
                                cur.execute("delete from ipm_project_team_junction where project_team_id = :1",(e["IPM_PROJECT_TEAM_ID"],))
                                cur.execute("delete from ipm_project_team where id = :1",(e["IPM_PROJECT_TEAM_ID"],))
                                con.commit()
                        
                        # update team_id
                        cur.execute("select * from view_ipm_project_team where project_id = :1 and team_id is not null",(project_id,))
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        existingMemberUpdated = cur.fetchall()

                        for f in existingMemberUpdated:
                            if "TEAM_ID" in f :
                                updateRow = cur.execute("select * from ipm_project_team where id = :1",(f["IPM_PROJECT_TEAM_ID"],)).fetchone()
                                updateRowId = updateRow[0]
                                cur.execute("UPDATE ipm_project_team SET team_id = IPM_PROJECT_TEAM_SEQ.currval WHERE ID = :2",(updateRowId,))
                                con.commit()
                                    
                    # END: set an EXISTING member to be the manager
                                    
                    # START: set a NEW member to be the manager
                                    
                    if int(chosen_manager_emp_id) not in existingMemberEmpIdList:
                        print("new member jdi PM")

                        cur.execute(
                            """
                            INSERT INTO ipm_project_team
                            (id, team_id, user_id)
                            VALUES
                            (IPM_PROJECT_TEAM_SEQ.nextval, :1, :2)
                            """,
                            (None,chosen_manager_emp_id,)
                        )
                        con.commit()

                        cur.execute(
                            """
                            INSERT INTO ipm_project_team_junction
                            (id, project_team_id, project_id)
                            VALUES
                            (IPM_PROJECT_TEAM_JUNCTION_SEQ.nextval, IPM_PROJECT_TEAM_SEQ.currval, :1)
                            """,
                            (project_id,)
                        )   
                        con.commit()

                        # update team_id
                        cur.execute("select * from view_ipm_project_team where project_id = :1 and team_id is not null",(project_id,))
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        existingMemberUpdated = cur.fetchall()
                        
                        for e in existingMemberUpdated:
                            if "TEAM_ID" in e:
                                updateRow = cur.execute("select * from ipm_project_team where id = :1",(e["IPM_PROJECT_TEAM_ID"],)).fetchone()
                                updateRowId = updateRow[0]
                                cur.execute("UPDATE ipm_project_team SET team_id = IPM_PROJECT_TEAM_SEQ.currval WHERE ID = :2",(updateRowId,))
                        
                        con.commit()
                                
                    # END: set a NEW member to be the manager
                
                con.commit()

                return render_template(
                    "index.html", name=session["fname"], projects=data1, users=data2, all_duration=data3
                )

            # get TEAM MEMBER for dropdown in modal ADD TEAM MEMBER
            if request.form["d_action"] == "get_team_member":
                project_id = request.form["project_id"]

                cur.execute("""
                    SELECT u.id, u.first_name || ' ' || u.last_name as full_name FROM ipm_user u WHERE u.id NOT IN
                    (SELECT t.user_id FROM ipm_project_team t JOIN ipm_project_team_junction j ON j.project_team_id = t.id WHERE t.team_id IS NULL AND j.project_id = :1)
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                teamMemberOption = cur.fetchall()

                cur.execute("""
                    SELECT u.first_name || ' ' || u.last_name as full_name, u.id
                    FROM ipm_user u 
                    JOIN ipm_project_team t ON u.id = t.user_id 
                    JOIN ipm_project_team_junction j ON j.project_team_id = t.id
                    WHERE project_id = :1 AND t.team_id IS NOT NULL
                    """,
                    (project_id,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                teamMember = cur.fetchall()
                
                userArr = []
                for user in teamMember:
                    userArr.append(int(user["ID"]))

                return (
                    json.dumps({
                        "data": "sucess",
                        "teamMemberOption": teamMemberOption,
                        "userArr": userArr
                    }), 
                    200,
                    {"ContentType": "application/json"},
                )

            if request.form["d_action"] == "save_team":
                input_TM = json.loads(request.form["inputTM"])
                team_project_id = request.form["team_project_id"]
                
                # Team HAS NO MEMBER
                if input_TM is None:

                    cur.execute("select * from ipm_project_team_junction where project_id = :1",[team_project_id])
                    columns = [col[0] for col in cur.description]
                    cur.rowfactory = lambda *args: dict(zip(columns, args))
                    existingMember = cur.fetchall()

                    for a in existingMember:
                        table_team_id = a["PROJECT_TEAM_ID"]
                        row_table_team = cur.execute("select * from ipm_project_team where id = :1",(table_team_id,)).fetchone()
                        # delete team member only
                        if row_table_team[1] != None:
                            user_id = row_table_team[2]
                            cur.execute("""
                                delete from ipm_specification sp 
                                where sp.id IN 
                                    (SELECT sp.id FROM ipm_specification sp 
                                    join ipm_scope sc on sc.id = sp.scope_id 
                                    join ipm_project p on p.id = sc.project_id
                                    where p.id = :1 and assigned_user_id = :2)
                                """,
                                (team_project_id, user_id,)
                            )
                            cur.execute("delete from ipm_project_team_junction where id = :1",(a["ID"],))
                            cur.execute("delete from ipm_project_team where id = :1",(row_table_team[0],))

                    con.commit()
                
                # Team HAS MEMBER
                elif input_TM != None:
                    # Save team member

                    cur.execute("""
                        SELECT t.user_id, u.first_name || ' ' || u.last_name as full_name, t.id FROM ipm_project_team t 
                        JOIN ipm_project_team_junction j ON j.project_team_id = t.id JOIN ipm_user u ON u.id = t.user_id 
                        WHERE j.project_id = :1 AND t.team_id IS NOT NULL
                        """,
                        (team_project_id,)
                    )
                    columns = [col[0] for col in cur.description]
                    cur.rowfactory = lambda *args: dict(zip(columns, args))
                    existingMember = cur.fetchall()

                    newMemberArr = []
                    existingMemberArr = []
                    for a in input_TM:
                        newMemberArr.append(int(a))
                    for b in existingMember:
                        existingMemberArr.append(int(b["USER_ID"]))
                    for newMember in newMemberArr:
                        inDB = False
                        for existingMember in existingMemberArr:
                            if newMember == existingMember:
                                existingMemberArr.remove(existingMember)
                                inDB = True
                                break
                        if inDB == False:
                            cur.execute("""
                                SELECT t.id FROM ipm_project_team t 
                                JOIN ipm_project_team_junction j ON j.project_team_id = t.id
                                JOIN ipm_user u ON u.id = t.user_id
                                WHERE j.project_id = :1 AND t.team_id IS NULL   
                                """,
                                (team_project_id,)
                            )
                            columns = [col[0] for col in cur.description]
                            cur.rowfactory = lambda *args: dict(zip(columns, args))
                            team_id = cur.fetchall()

                            for a in team_id:
                                team_id = a["ID"]
                            if team_id:
                                cur.execute(
                                    """
                                    INSERT INTO ipm_project_team
                                    (id, team_id, user_id)
                                    VALUES
                                    (ipm_project_team_seq.nextval, :1, :2)
                                    """,
                                    (team_id,newMember,)
                                )
                            else: 
                                cur.execute(
                                    """
                                    INSERT INTO ipm_project_team
                                    (id, team_id, user_id)
                                    VALUES
                                    (ipm_project_team_seq.nextval, :1, :2)
                                    """,
                                    (0,newMember,)
                                )
                            
                            con.commit()

                            promTeamId = cur.execute("SELECT * FROM (SELECT * FROM ipm_project_team ORDER BY id DESC) WHERE ROWNUM <= 1").fetchone()
                            cur.execute(
                                """
                                INSERT INTO ipm_project_team_junction
                                (id, project_team_id, project_id)
                                VALUES
                                (ipm_project_team_junction_seq.nextval, :1, :2)
                                """,
                                (promTeamId[0],team_project_id,)
                            )
                            con.commit()
                            
                    # Delete team member from DB
                    for a in existingMemberArr:

                        cur.execute("""
                            SELECT t.id AS table_team_id, j.id AS table_junction_id FROM ipm_project_team t JOIN ipm_project_team_junction j ON j.project_team_id = t.id 
                            WHERE t.user_id = :1 AND j.project_id = :2  
                            """,
                            (a,team_project_id,)
                        )
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        rowToBeDeleted = cur.fetchall()

                        for b in rowToBeDeleted:
                            table_team = cur.execute("select * from ipm_project_team where id = :1",(b["TABLE_TEAM_ID"],)).fetchone()
                            user_id = table_team[2]

                            cur.execute("""
                                delete from ipm_specification sp 
                                where sp.id IN 
                                    (SELECT sp.id FROM ipm_specification sp 
                                    join ipm_scope sc on sc.id = sp.scope_id 
                                    join ipm_project p on p.id = sc.project_id
                                    where p.id = :1 and assigned_user_id = :2)
                                """,
                                (team_project_id, user_id,)
                            )
                            cur.execute("delete from ipm_project_team_junction where id = :1",(b["TABLE_JUNCTION_ID"],))
                            cur.execute("delete from ipm_project_team where id = :1",(table_team[0],))
                        
                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            if request.form["d_action"] == "scope_save":
                project_id = request.form["project_id"]

                form_data = request.form["data_form"]
                scdata = json.loads(form_data)

                scpid = scdata["project_id_in_scope"]
                scn = scdata["scope_name"]
                scsd = scdata["scope_start"]
                sced = scdata["scope_end"]
                scd = scdata["scope_desc"]
            
                cur.execute(
                    """
                    INSERT INTO ipm_scope 
                    (id, name, planned_start_date, planned_end_date, note, scope_id_custom, project_id)
                    VALUES
                    (IPM_scope_SEQ.nextval, :name, TO_DATE(:planned_start_date,'fxYYYY-MM-DD'), TO_DATE(:planned_end_date,'fxYYYY-MM-DD'), :note, CONCAT('sc', IPM_scope_SEQ.currval), :project_id)
                    """,
                    name = scn,
                    planned_start_date = scsd,
                    planned_end_date = sced,
                    note = scd,
                    project_id = scpid
                )
                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            if request.form["d_action"] == "insert_new_spec":
                spdata = json.loads(request.form["data_form"])

                spn = spdata["name"]
                spd = spdata["desc"]
                spdur = spdata["duration"]
                spuid = spdata["assignedPerson"]
                spscid = spdata["scope"]

                cur.execute(
                    """
                    INSERT INTO ipm_specification 
                    (
                        id, 
                        name, 
                        description, 
                        added_date, 
                        percentage, 
                        spec_id_custom, 
                        scope_id, 
                        status_id, 
                        duration_id, 
                        assigned_user_id
                    )
                    VALUES
                    (
                        ipm_specification_SEQ.nextval, 
                        :name, 
                        :description, 
                        sysdate, 
                        0, 
                        CONCAT('sp', ipm_specification_SEQ.currval),
                        :scope_id, 
                        1, 
                        :duration_id, 
                        :assigned_user_id
                    )
                    """,
                    name = spn,
                    description = spd,
                    scope_id = spscid,
                    duration_id = spdur, 
                    assigned_user_id = spuid
                )
                con.commit()

                return (json.dumps({ "data": "success" }), 200,{ "ContentType": "application/json" },)

            # GET data for PROJECT when PROJECT in OVERALL PROJECT VIEW TREE is clicked
            if request.form["d_action"] == "get_project":
                project_id_custom = request.form["id_project"]
                
                project = cur.execute("select * from ipm_project where project_id_custom = :1",(project_id_custom,)).fetchone()
                project_id = project[0]
                name = project[1]
                desc = project[5]
                start = project[3]
                end = project[4]
            
                return (
                    json.dumps({
                        "project_id": project_id,
                        "name": name,
                        "note": desc,
                        "start": start.isoformat(),
                        "end": end.isoformat()
                    }),
                    200,
                    {"ContentType": "application/json"},
                )

            # UPDATE PROJECT (TREE)
            if request.form["d_action"] == "update_project":
                form_data = json.loads(request.form["formData"])
                    
                project_id = form_data["project_id"]
                name = form_data["project_name"]
                desc = form_data["project_desc"]
                start = form_data["project_start"]
                end = form_data["project_end"]

                cur.execute("""
                    UPDATE ipm_project
                    SET 
                        name = :name,
                        description = :description,
                        planned_start_date = TO_DATE(:planned_start_date,'fxYYYY-MM-DD'),
                        planned_end_date = TO_DATE(:planned_end_date,'fxYYYY-MM-DD'),
                        note = :description
                    WHERE id = :id
                    """,
                    name= name,
                    description= desc,
                    planned_start_date= start,
                    planned_end_date= end,
                    id= project_id
                )

                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)
                
            # DELETE PROJECT (TREE)
            if request.form["d_action"] == "delete_project":
                pid = request.form["project_id"]

                cur.execute("select * from ipm_scope where project_id = :1",(pid,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_scope = cur.fetchall()

                if all_scope:
                    for sc in all_scope:
                        cur.execute("select * from ipm_specification where scope_id = :1",(sc["ID"],))
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        all_spec = cur.fetchall()

                        if all_spec:
                            for sp in all_spec:
                                cur.execute("delete from ipm_specification where id = :1",(sp["ID"],))

                        cur.execute("delete from ipm_scope where id = :1",(sc["ID"],))

                cur.execute("select * from ipm_project_team_junction where project_id = :1",(pid,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_project_team = cur.fetchall()

                if all_project_team:
                    for pt in all_project_team:
                        cur.execute("delete from ipm_project_team_junction where id = :1",(pt["ID"],))
                        cur.execute("delete from ipm_project_team where id = :1",(pt["PROJECT_TEAM_ID"],))

                cur.execute("select * from ipm_file_category where project_id = :1",(pid,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_folder = cur.fetchall()

                if all_folder:
                    for f in all_folder:
                        cur.execute("select * from ipm_project_file where file_category_id = :1",(f["FILE_CATEGORY_ID_CUSTOM"],))
                        columns = [col[0] for col in cur.description]
                        cur.rowfactory = lambda *args: dict(zip(columns, args))
                        all_files = cur.fetchall()

                        if all_files:
                            cur.execute("delete from ipm_project_file where file_category_id = :1",(f["FILE_CATEGORY_ID_CUSTOM"],))

                        cur.execute("delete from ipm_file_category where id = :1",(f["ID"],))
                
                pub = cur.execute("select * from ipm_project_public where project_id = :1",(pid,)).fetchone()
                pri = cur.execute("select * from ipm_project_private where project_id = :1",(pid,)).fetchone()

                if pub == None:
                    cur.execute("delete from ipm_project_private where project_id = :1",(pid,))
                elif pri == None:
                    cur.execute("delete from ipm_project_public where project_id = :1",(pid,))

                cur.execute("delete from ipm_project where id = :1",(pid,))

                con.commit()
                
                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)
            
            # GET data for SCOPE when any SCOPE in OVERALL PROJECT VIEW TREE is clicked
            if request.form["d_action"] == "get_scope":
                scope_id_custom = request.form["id_scope"]
                sc = cur.execute("select * from ipm_scope where scope_id_custom = :1",(scope_id_custom,)).fetchone()
                scope_id = sc[0]
                name = sc[1]
                note = sc[4]
                start = sc[2]
                end = sc[3]

                return (
                    json.dumps({
                        "scope_id": scope_id,
                        "name": name,
                        "note": note,
                        "start": start.isoformat(),
                        "end": end.isoformat()
                    }),
                    200,
                    {"ContentType": "application/json"},
                )
            
            # UPDATE SCOPE (TREE)  
            if request.form["d_action"] == "update_scope":
                scd = json.loads(request.form["data_form"])
                
                name = scd["name"]
                note = scd["desc"]
                start = scd["start"]
                end = scd["end"]
                scid = scd["scope_id"]
                
                cur.execute("""
                    UPDATE ipm_scope
                    SET 
                        name = :name,
                        planned_start_date = TO_DATE(:planned_start_date,'fxYYYY-MM-DD'),
                        planned_end_date = TO_DATE(:planned_end_date,'fxYYYY-MM-DD'),
                        note = :note
                    WHERE id = :id
                    """, 
                    name= name,
                    planned_start_date= start,
                    planned_end_date= end,
                    note= note,
                    id= scid
                )

                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            # DELETE SCOPE (TREE)
            if request.form["d_action"] == "delete_scope":
                scope_id = request.form["scope_id"]
                
                cur.execute("select * from ipm_specification where scope_id = :1",(scope_id,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                spec_all = cur.fetchall()

                if spec_all:
                    for s in spec_all:
                        cur.execute("delete from ipm_specification where id = :1",(s["ID"],))

                cur.execute("delete from ipm_scope where id = :1",(scope_id,))

                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            # GET data for SPEC. when any SPEC. in OVERALL PROJECT VIEW TREE is clicked
            if request.form["d_action"] == "get_spec":
                spec_id_custom = request.form["id_spec"]

                cur.execute("""
                    select
                        id spid, 
                        name spname,
                        description spdesc, 
                        scope_id scid, 
                        duration_id spdur, 
                        assigned_user_id spuser
                    from ipm_specification
                    where spec_id_custom = :1
                    """,
                    (spec_id_custom,)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                data_for_modal = cur.fetchall()

                sp = cur.execute("select * from ipm_specification where spec_id_custom = :1",(spec_id_custom,)).fetchone()
                sc = cur.execute("select * from ipm_scope where id = :1",(sp[6],)).fetchone()
                project = cur.execute("select * from ipm_project where id = :1",(sc[6],)).fetchone()

                cur.execute("select id, name from ipm_scope where project_id = :1",(sc[6],))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                all_scope = cur.fetchall()

                cur.execute("select * from ipm_ref_duration")
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                duration_all = cur.fetchall()

                cur.execute("""
                    SELECT u.first_name || ' ' || u.last_name as full_name, u.id
                    FROM ipm_user u
                    JOIN ipm_project_team t ON u.id = t.user_id
                    JOIN ipm_project_team_junction j ON j.project_team_id = t.id
                    WHERE j.project_id = :1
                    """,
                    (project[0],)
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                teamMember = cur.fetchall()

                return (
                    json.dumps({
                        "modal_data": data_for_modal,
                        "scope_all": all_scope,
                        "duration_all": duration_all,
                        "teamMember": teamMember
                    }),
                    200,
                    {"ContentType": "application/json"},
                )
            
            # UPDATE SPEC. (TREE)
            if request.form["d_action"] == "spec_update":
                spd = json.loads(request.form["data_form"])
                
                name = spd["name"]
                desc = spd["desc"]
                id_scope = spd["scope"]
                duration = spd["duration"]
                person = spd["assignedPerson"]
                id_spec = spd["specId"]
                
                cur.execute("""
                    UPDATE ipm_specification
                    SET 
                        name = :name,
                        description = :description,
                        scope_id = :scope_id,
                        duration_id = :duration_id,
                        assigned_user_id = :assigned_user_id
                    WHERE id = :id
                    """, 
                    name= name,
                    description= desc,
                    scope_id= id_scope,
                    duration_id= duration,
                    assigned_user_id= person,
                    id= id_spec
                )

                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)
                
            # DELETE SPEC. (TREE)
            if request.form["d_action"] == "delete_spec":
                id_spec = request.form["data_form"]
                cur.execute("delete from ipm_specification where id = :1",(id_spec,))
                con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            if request.form["d_action"] == "createFolderRoot":
                cur.execute(
                    """
                    INSERT INTO ipm_file_category 
                    (
                        id, 
                        name, 
                        file_category_id_custom, 
                        parent_id, 
                        project_id
                    )
                    VALUES
                    (
                        ipm_file_category_SEQ.nextval, 
                        :name, 
                        CONCAT('folder_', ipm_file_category_SEQ.currval),
                        :parent_id,
                        :project_id
                    )
                    """,
                    name = request.form["name"],
                    parent_id = None,
                    project_id = request.form["projectId"]
                )
                con.commit()

                latest_inserted_folder = cur.execute("select * from ipm_file_category where rownum = 1 order by id desc").fetchone()
                file_category_id_custom = 'folder_' + str(latest_inserted_folder[0])

                return (json.dumps({ 
                        "data": "success",
                        "file_category_id_custom": file_category_id_custom
                    }), 
                    200,
                    { "ContentType": "application/json" },
                )

            if request.form["d_action"] == "createFolderChild":
                cur.execute(
                    """
                    INSERT INTO ipm_file_category 
                    (
                        id, 
                        name, 
                        file_category_id_custom, 
                        parent_id, 
                        project_id
                    )
                    VALUES
                    (
                        ipm_file_category_SEQ.nextval, 
                        :name, 
                        CONCAT('folder_', ipm_file_category_SEQ.currval),
                        :parent_id,
                        :project_id
                    )
                    """,
                    name = request.form["name"],
                    parent_id = request.form["parent_id"],
                    project_id = request.form["projectId"]
                )
                con.commit()

                latest_inserted_folder = cur.execute("select * from ipm_file_category where rownum = 1 order by id desc").fetchone()
                file_category_id_custom = 'folder_' + str(latest_inserted_folder[0])

                return (json.dumps({ 
                        "data": "success",
                        "file_category_id_custom": file_category_id_custom
                    }), 
                    200,
                    { "ContentType": "application/json" },
                )

            if request.form["d_action"] == "uploadFile":
                if "file_data" in request.files:
                    file = request.files["file_data"]

                    file_data = file.read()

                    # Retrieve the filename
                    filename = file.filename

                    # Retrieve the file type
                    file_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

                    cur.execute(
                        """
                        INSERT INTO ipm_project_file
                        (
                            id, 
                            file_,
                            file_name,
                            file_type,
                            file_id_custom,
                            project_id,
                            file_category_id
                        )
                        VALUES
                        (
                            IPM_PROJECT_FILE_SEQ.nextval,
                            :file_data,
                            :file_name,
                            :file_type,
                            CONCAT('file_', IPM_PROJECT_FILE_SEQ.currval),
                            :project_id,
                            :file_category_id
                        )
                        """,
                        file_data = file_data,
                        file_name = filename,
                        file_type = file_type,
                        project_id = request.form["project_id_upload"],
                        file_category_id  = request.form["file_category_id"]
                    )
                    con.commit()

                return render_template(
                    "index.html", name=session["fname"], projects=data1, users=data2, all_duration=data3
                )

            if request.form["d_action"] == "deleteFile":
                fileArr = json.loads(request.form["fileDeleteArr"])
                fileArrList = []
                for a in fileArr:
                    fileArrList.append(str(a))
                    
                for fileId in fileArrList:
                    if fileId.startswith('folder_'):
                        folder = cur.execute("select * from ipm_file_category where file_category_id_custom = :1",(fileId,)).fetchone()

                        if folder:
                            cur.execute("delete from ipm_project_file where file_category_id = :1",(folder[2],))

                        cur.execute("delete from ipm_file_category where file_category_id_custom = :1",(fileId,))

                    elif fileId.startswith('file_'):
                        cur.execute("delete from ipm_project_file where file_id_custom = :1",(fileId,))

                    con.commit()

                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            if request.form["d_action"] == "updateTree":
                tree_data = json.loads(request.form["treeData"])

                for a in tree_data:
                    parent = str(a.get("parent"))
                    a_attr_href = str(a.get('a_attr', {}).get('href'))
                    # under a folder
                    if (parent != '#'):
                        # a file under folder
                        if (a_attr_href != '#'):
                            cur.execute("""
                                UPDATE ipm_project_file
                                SET 
                                    file_name = :file_name,
                                    file_category_id = :file_category_id
                                WHERE file_id_custom = :file_id_custom
                                """,
                                file_name = a.get("text"),
                                file_category_id = a.get("parent"),
                                file_id_custom = a.get("id")
                            )
                            con.commit()
                        # a folder under folder
                        else:
                            cur.execute("""
                                UPDATE ipm_file_category
                                SET 
                                    name = :name,
                                    parent_id = :parent_id
                                WHERE file_category_id_custom = :file_category_id_custom
                                """,
                                name = a.get("text"),
                                parent_id = a.get("parent"),
                                file_category_id_custom = a.get("id")
                            )
                            con.commit()
                    # a root folder
                    else:
                        cur.execute("""
                            UPDATE ipm_file_category
                            SET 
                                name = :name,
                                parent_id = :parent_id
                            WHERE file_category_id_custom = :file_category_id_custom
                            """,
                            name = a.get("text"),
                            parent_id = None,
                            file_category_id_custom = a.get("id")
                        )
                        con.commit()
                        
                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)

            # START GET SPEC
            if request.form["d_action"] == "getSpec":
                spec_data = json.loads(request.form["iid"])
                cur.execute("select name, description, scope_id, percentage from ipm_specification where id = :1", (spec_data,))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                spec_detail = cur.fetchall()

                return (
                    json.dumps({
                        "spec_detail": spec_detail
                    }),
                    200,
                    {"ContentType": "application/json"},
                )
            # END GET SPEC

            #START UPDATE SPEC.
            if request.form['d_action'] == "update_spec":
                form_data = json.loads(request.form['data_form'])
                project_id = request.form["project_id"]

                # check if spec. name is used
                spec_name = str(form_data["name"]).lower()
                cur.execute(
                    """
                    select s.name from ipm_project p join ipm_scope sc on p.id = sc.project_id
                    join ipm_specification s on sc.id = s.scope_id where p.id = :1 and s.id != :2
                    """, (project_id, form_data["specId"])
                )
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                allSpec = cur.fetchall()
                specExist = 0
                specNameList = []
                for spec in allSpec:
                    specNameList.append(str(spec.get("NAME")).lower())
                if (spec_name in specNameList):
                    specExist = 1
                    return (json.dumps({"specExist": 1}),200,{"ContentType": "application/json"},
                )
                    
                if(specExist == 0):
                    spec_id = form_data["specId"]
                    spec_name = form_data["name"]
                    spec_desc = form_data["desc"]
                    cur.execute("""
                            UPDATE ipm_specification
                            SET 
                                name = :1,
                                description = :2
                            WHERE id = :3
                            """,
                            (spec_name,spec_desc,spec_id)
                        )
                    con.commit()
                    return (json.dumps({"specExist": 0}), 200, {"ContentType": "application/json"},)
            #END UPDATE SPEC

            # UPDATE SPEC - SCOPE ONLY
            if request.form["d_action"] == "updateSpecScope":
                cur.execute("""
                            UPDATE ipm_specification
                            SET 
                                scope_id = :1
                            WHERE id = :2
                            """,
                            (int(request.form["specScope"]),int(request.form["specIdScope"]))
                        )
                con.commit()

            # UPDATE Assigned Person
            if request.form["d_action"] == "updateAssignedTo":
                cur.execute(
                    """
                    Update ipm_specification
                    SET
                        assigned_user_id = :1
                    WHERE id = :2
                    """,
                    (int(request.form["assignedEmp"]),int(request.form["specIdEmp"]))
                ) 
                con.commit()

            # UPDATE PECENTAGE
            if request.form["d_action"] == "update_percentage":
                data = json.loads(request.form["data"])
                cur.execute(
                     """
                     update ipm_specification 
                     SET
                        percentage = :1
                    WHERE id = :2
                     """,
                    (int(data["percentage"]), int(data["spec_id"]))
                )
                if int(data["percentage"]) == 100:
                    cur.execute(
                    """
                    update ipm_specification 
                    SET
                        status_id = :1
                    WHERE id = :2
                    """,
                    (3, int(data["spec_id"]))
                    )
                else:
                    cur.execute(
                    """
                    update ipm_specification 
                    SET
                        status_id = :1
                    WHERE id = :2
                    """,
                    (2, int(data["spec_id"]))
                    )
                con.commit()
                return (json.dumps({"data": "sucess"}), 200, {"ContentType": "application/json"},)
            
            # UPDATE START JOB
            if request.form["d_action"] == "start_job":
                cur.execute(
                    """
                    update ipm_specification
                    SET
                        status_id = :1
                    where id = :2
                    """, (2, int(request.form["spec_id"]))
                )
                con.commit()

            # DELETE SPEC
            if request.form["d_action"] == "remove_spec":
                cur.execute(
                    """
                    DELETE from ipm_specification where id = :1
                    """, (int(request.form["spec_id"]),)
                )
                con.commit()
        cur.close()

        return render_template(
            "index.html", name=session["fname"], projects=data1, users=data2, all_duration=data3
        )
    
    else:  # else go back to login
        return redirect(url_for("login"))

@app.route('/files/<file_id>', methods=['GET'])
def download_file(file_id):
    # Query the file data from the database
    with con.cursor() as cursor:
        cursor.execute("SELECT * FROM ipm_project_file WHERE id = :1",(file_id,))
        row = cursor.fetchone()
        if row:
            file_data = row[1].read()
            file_name = row[2]
            file_type = row[3]
        else:
            return "File not found"

    # Set the appropriate headers for the response
    headers = {
        'Content-Type': file_type,
        'Content-Disposition': 'attachment; filename=' + file_name
    }

    # Create the response with the file data and headers
    response = make_response(file_data)
    response.headers = headers

    return response

    # Serve the file for download
    # return send_file(file_data, mimetype=file_type, download_name=file_name, as_attachment=True)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data_submit = request.form["format_data"]
        insert_data = json.loads(data_submit)
        fname = insert_data["fname"]
        lname = insert_data["lname"]
        email = insert_data["email"]
        password = insert_data["password"]
        # Hash the password using MD5
        password_hash = hashlib.md5(password.encode()).hexdigest()

        cur = con.cursor()
        query = "SELECT email FROM ipm_user"
        username_all = cur.execute(query)

        if username_all:
            detail = cur.fetchall()  # fecth all data
            for user_email in detail:
                if email in user_email:  # check existing data
                    return (
                        json.dumps({"data": "fail"}),
                        200,
                        {"ContentType": "application/json"},
                    )  # send back through AJAX (FAIL)
            # cur = con.cursor()
            cur.execute(
                """
                INSERT INTO ipm_user 
                (id, email, password, first_name, last_name) 
                VALUES 
                (IPM_USER_SEQ.nextval, :2, :3, :4, :5)""",
                (email, password_hash, fname, lname),
            )

            con.commit()
            cur.close()
            return (
                json.dumps({"data": "sucess"}),
                200,
                {"ContentType": "application/json"},
            )  # send back through AJAX (SUCESS)
        else:
            # cur = con.cursor()
            cur.execute(
                """
                INSERT INTO ipm_user 
                (id, email, password, first_name, last_name) 
                VALUES 
                (IPM_USER_SEQ.nextval, :2, :3, :4, :5)""",
                (email, password_hash, fname, lname),
            )
            con.commit()
            cur.close()
            return (
                json.dumps({"data": "sucess"}),
                200,
                {"ContentType": "application/json"},
            )  # send back through AJAX (SUCESS)

    return render_template(
        "register.html"
    )  # click Link (after register redirect to login using javascript)

@app.route("/login")
def logout():
    session.clear()  # clear session
    return redirect(url_for("login"))  # go to login page


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        if request.form["d_action"] == "update_user":
            user_data = request.form["user_data"]
            insert_data = json.loads(user_data)
            fname = insert_data["fname"]
            lname = insert_data["lname"]
            email = insert_data["email"]
            # UPDATE DETAIL
            cur = con.cursor()
            cur.execute(
                """
                UPDATE ipm_user
                        SET email = :1,
                            first_name = :2,
                            Last_name = : 3
                        WHERE ID = :4

                """, (email,fname,lname,session["user_id"]))
            con.commit()
            
            cur.execute("select email, first_name, last_name from ipm_user where id = :1", (session["user_id"],))
            columns = [col[0] for col in cur.description]
            cur.rowfactory = lambda *args: dict(zip(columns, args))
            user_detail = cur.fetchall()
        
            # SET SESSION AFTER UPDATE DETAIL
            session["fname"] = user_detail[0].get("FIRST_NAME")
            session["lname"] = user_detail[0].get("LAST_NAME")
            session["email"] = user_detail[0].get("EMAIL")

            return(
                json.dumps({"data": "success"}),
                200,
                {"ContentType": "application/json"},
            )

   
    return render_template(
        "profile.html",
        name=session["fname"],
        lname=session["lname"],
        email=session["email"],
    )

@app.route("/Project-List", methods=["GET", "POST"])
def project_list():

    cur = con.cursor()
    user_id = session["user_id"]  #Type int
    cur.execute(
        """
        SELECT DISTINCT p.*,
        (CASE 
            WHEN user_id = :1 THEN 'joined'
            ELSE 'not join'
        END) AS Result,
        (CASE 
            WHEN pub.request_to_join IS NULL THEN 'Private'
            WHEN pub.request_to_join = '1' THEN 'Public (Request)'
            ELSE 'Public'
        END) AS STATUS
        FROM ipm_project p
        LEFT JOIN ipm_project_public pub ON pub.project_id = p.id
        LEFT JOIN ipm_project_private pri ON pri.project_id = p.id
        JOIN ipm_project_team_junction pt ON p.id = pt.project_id
        JOIN ipm_project_team i ON i.id = pt.project_team_id
        ORDER BY p.id ASC
        
        """, (user_id,)
    )
    
    columns = [col[0] for col in cur.description]
    cur.rowfactory = lambda *args: dict(zip(columns, args))
    all_projects = cur.fetchall()

    temp = []
    result = []
    num = 1
    for i in all_projects:
        i["iter"] = num
        temp.append(i.get("ID"))
        if temp.count(i.get("ID")) > 1:
            if i.get("RESULT") == "joined":
                result.append(i)
                num += 1
            else:
                i.clear()
        else:
            result.append(i)
            num += 1

    # Get Notification
    cur.execute(
        """
        select p.name as project_name, n.id as noti_id, p.id as project_id,u.id as user_id, u.first_name ||' '|| u.last_name as full_name from ipm_project p join ipm_project_team_junction j on p.id = j.project_id
        join ipm_project_team t on t.id = j.project_team_id join ipm_notification n on n.id_project = p.id join ipm_user u on u.id = n.user_id_request
        where p.id in (select n.id_project from ipm_notification n join ipm_project p on n.id_project = p.id) and t.team_id is null and t.user_id = :1
        """,(user_id,))
    
    columns = [col[0] for col in cur.description]
    cur.rowfactory = lambda *args: dict(zip(columns, args))
    notification = cur.fetchall()
    test = notification
    count_noti = len(test)
    if request.method == "POST":

        # Accecpt request and delete the notification
        if request.form["d_action"] == "accept_request":
            print(request.form["noti_id"])
            id_project_request = request.form["project_id_accept"]
            user_id_request = request.form["user_id_request"]
            noti_id = request.form["noti_id"]
            cur.execute(
                """
                SELECT p.name, j.project_team_id as team_id from ipm_project p join ipm_project_team_junction j on p.id = j.project_id
                where p.id = :1
                
                """,(id_project_request,)
            )
            columns = [col[0] for col in cur.description]
            cur.rowfactory = lambda *args: dict(zip(columns, args))
            project_req = cur.fetchall()

            cur.execute("INSERT INTO ipm_project_team values(ipm_project_team_SEQ.nextval, :2, :3)",(project_req[0].get("TEAM_ID"), user_id_request))
            con.commit()

            cur.execute("SELECT id FROM ipm_project_team WHERE ROWNUM <= 1 ORDER BY id DESC")
            columns = [col[0] for col in cur.description]
            cur.rowfactory = lambda *args: dict(zip(columns, args))
            team_id_req = cur.fetchall()

            cur.execute(
                """
                INSERT INTO ipm_project_team_junction values(ipm_project_team_junction_SEQ.nextval,:2, :3)
                """, (team_id_req[0].get("ID"), id_project_request)
            )
            con.commit()

            cur.execute(
                """
                Delete from ipm_notification where id =: 1
                """, (int(noti_id),)
            )
            con.commit()
            return(
                json.dumps({"data": "success"}),
                200,
                {"ContentType": "application/json"},
            )
        if request.form["d_action"] == "request_exist":
                project_id = request.form["project_id"]
                cur.execute("select * from ipm_notification where id_project  = :1 and user_id_request = :2", (project_id, user_id))
                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                noti = cur.fetchall()

                if len(noti) > 0:
                    return(
                        json.dumps({"data": "exist"}),
                        200,
                        {"ContentType": "application/json"},
                    )
                else:
                    return(
                        json.dumps({"data": "not"}),
                        200,
                        {"ContentType": "application/json"},
                    )
        if request.form["d_action"] == "join_public_project":
            project_id = request.form["project_id"]
            cur.execute(
                """
                    SELECT p.name, j.project_team_id as team_id from ipm_project p join ipm_project_team_junction j on p.id = j.project_id
                    where p.id = :1
                """,(project_id,)
                )
            columns = [col[0] for col in cur.description]
            cur.rowfactory = lambda *args: dict(zip(columns, args))
            public = cur.fetchall()
            cur.execute("INSERT INTO ipm_project_team values(ipm_project_team_SEQ.nextval, :2, :3)",(public[0].get("TEAM_ID"), user_id))
            con.commit()

            cur.execute("SELECT id FROM ipm_project_team WHERE ROWNUM <= 1 ORDER BY id DESC")
            columns = [col[0] for col in cur.description]
            cur.rowfactory = lambda *args: dict(zip(columns, args))
            team_id = cur.fetchall()

            cur.execute(
                """
                INSERT INTO ipm_project_team_junction values(ipm_project_team_junction_SEQ.nextval,:2, :3)
                """, (team_id[0].get("ID"), project_id)
            )
            con.commit()
            return(
                json.dumps({"data": "success"}),
                200,
                {"ContentType": "application/json"},
            )



        if request.form["d_action"] == "insert_password_private":
            access = request.form["access"]
            if access == "Private":
                project_id = request.form["project_id"]
                password = request.form["pass"]
                password_hash = hashlib.md5(password.encode()).hexdigest()

                cur.execute( #j.id
                    """
                    select pri.*, j.project_team_id as team_id from ipm_project_private pri join ipm_project p on p.id = pri.project_id
                    join ipm_project_team_junction j on j.project_id = p.id 
                    where pri.project_id = :1
                    AND pri.Password = :2
                    """, (project_id, password_hash)
                )

                columns = [col[0] for col in cur.description]
                cur.rowfactory = lambda *args: dict(zip(columns, args))
                project_private = cur.fetchall()

                if len(project_private) > 0:
                    cur.execute(
                        """
                            INSERT INTO ipm_project_team values(ipm_project_team_SEQ.nextval, :2, :3)
                        """, (project_private[0].get("TEAM_ID"), user_id)
                    )
                    con.commit()

                    cur.execute("SELECT id FROM ipm_project_team WHERE ROWNUM <= 1 ORDER BY id DESC")
                    columns = [col[0] for col in cur.description]
                    cur.rowfactory = lambda *args: dict(zip(columns, args))
                    team_id = cur.fetchall()

                    cur.execute(
                        """
                        INSERT INTO ipm_project_team_junction values(ipm_project_team_junction_SEQ.nextval,:2, :3)
                        """, (team_id[0].get("ID"), project_id)
                        )
                    con.commit()

                    return (
                        json.dumps({"data": "success"}),
                        200,
                        {"ContentType": "application/json"},
                        )
                return(
                    json.dumps({"data": "wrong"}),
                    200,
                    {"ContentType": "application/json"},
                ) 
            
        if request.form["d_action"] == "insert_noti":
                project_id = request.form["project_id"]
                cur.execute(
                    """
                    INSERT INTO ipm_notification values(ipm_notification_SEQ.nextval, :2, :3, :4)
                    """,(project_id, user_id, 0)
                )

                con.commit()
                return(
                    json.dumps({"data": "success"}),
                    200,
                    {"ContentType": "application/json"},
                ) 
            
    cur.close()
    return render_template(
        "project_list.html",
        user_id = session["user_id"],
        name = session["fname"],
        lname = session["lname"],
        email = session["email"],
        projects = result,
        notification = notification,
        count_noti = count_noti
    )


if __name__ == "__main__":
    app.run(debug=True)  # debug moode don't change parameter
    # app.run()
    # app.run(
    #     debug=True,
    #     passthrough_errors=True,
    #     use_debugger=False,
    #     use_reloader=False
    # )
