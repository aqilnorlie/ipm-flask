from flask import Flask, render_template, session, redirect, url_for
from flask import request
import os, json
import oracledb
import hashlib

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("secret_key") #set your own secret key 

oracledb.init_oracle_client(lib_dir=r"C:\instantclient_21_10") # install oracle client and set variable
con = oracledb.connect(user=os.environ.get("oracle_user"), password=os.environ.get("oracle_pass"), 
                       dsn=os.environ.get("oracle_dns"), port=os.environ.get("oracle_port"))

print(con.is_healthy()) # check connection
cur = con.cursor()

@app.route("/dashboard")
def dashboard():
    if "email" in session:
        # session.clear()
        print(session["email"])
        return render_template("index.html", name=session['fname'])
    else: # else go back to login
        return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data_submit = request.form['format_data']
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
            detail = cur.fetchall() # fecth all data 
            for user_email in detail:
                if email in user_email: # check existing data
                    return json.dumps({'data': 'fail'}), 200, {'ContentType': 'application/json'} # send back through AJAX (FAIL)
            # cur = con.cursor()
            cur.execute("INSERT INTO ipm_user (id, email, password, first_name, last_name) VALUES (user_id_sequence.nextval, :2, :3, :4, :5)",
            (email, password_hash, fname, lname))

            con.commit()
            cur.close()
            return json.dumps({'data': 'sucess'}), 200, {'ContentType': 'application/json'}  # send back through AJAX (SUCESS)
        else:
            # cur = con.cursor()
            cur.execute("INSERT INTO ipm_user (id, email, password, first_name, last_name) VALUES (user_id_sequence.nextval, :2, :3, :4, :5)",
            (email, password_hash, fname, lname))
            con.commit()
            cur.close()
            return json.dumps({'data': 'sucess'}), 200, {'ContentType': 'application/json'}  # send back through AJAX (SUCESS)

    return render_template("register.html") # click Link (after register redirect to login using javascript)

@app.route("/",  methods=["GET", "POST"])
def login():
    if "email" in session:
        return redirect(url_for("dasboard"))
    
    if request.method == "POST":
        email = request.form["email"] # get data from email input
        password = request.form["password"] # get data from password input
        password_hash = hashlib.md5(password.encode()).hexdigest()
        cur = con.cursor()
        user_info = cur.execute("SELECT first_name, last_name, email FROM ipm_user WHERE email = :1 AND password = :2",(email, password_hash)) 
        if user_info:
            detail = user_info.fetchall()
            for fname, lname, email in detail:
                session["fname"] = fname # insert name into session
                session["lname"] = lname
                session["email"] = email
                return redirect(url_for("dashboard"))
            
    return render_template("login.html")

# LOGOUT FUNCTION
@app.route("/login")
def logout():
    session.clear() # clear session
    return redirect(url_for("login")) # go to login page

@app.route("/profile")
def profile():
    return render_template("profile.html")

if __name__ == "__main__":
    app.run(debug=True) # debug moode don't change parameter

