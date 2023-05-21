from flask import Flask, render_template, redirect, url_for
import os
import oracledb

app = Flask(__name__)

oracledb.init_oracle_client(lib_dir=r"C:\instantclient_21_10") # install oracle client and set variable
con = oracledb.connect(user=os.environ.get("oracle_user"), password=os.environ.get("oracle_pass"), 
                       dsn=os.environ.get("oracle_dns"), port=os.environ.get("oracle_port"))
print(con.is_healthy()) # check connection

# cur = con.cursor()
# cur.execute("select * from help")
# res = cur.fetchall()
# for i in res:
#     print(i)
# cur.close()
# con.close()

@app.route("/")
def dashboard():
    return render_template("index.html")

@app.route("/login")
def login(): 
    return render_template("login.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

if __name__ == "__main__":
    app.run(debug=True) # debug moode don't change parameter

