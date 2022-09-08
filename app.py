import json
import os
import random
import threading
import time
import socket
from flask import Flask, request, redirect, url_for, render_template, flash, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy

import job_view_api
import spider_51job

app = Flask(__name__)
base_dir = os.path.dirname(__file__)
path = os.path.join(base_dir, 'database.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 创建数据库sqlalchemy工具对象
db = SQLAlchemy(app)


class User(db.Model, UserMixin):
    """用户表"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(32), unique=True)  # 用户名
    password = db.Column(db.String(32))  # 密码
    is_admin = db.Column(db.Boolean, default=False)  # 是否为管理员，默认否


class Title(db.Model):
    """存储Mongodb表名的表"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(256), unique=True)  # Mongodb表名
    times = db.Column(db.Integer, default=0)  # 访问次数
    job = db.relationship("Job", backref="title", lazy='dynamic')


class Job(db.Model):
    """职位表，job+title唯一"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job = db.Column(db.String(1024))  # 职位
    times = db.Column(db.Integer, default=0)  # 访问次数
    title_id = db.Column(db.Integer, db.ForeignKey('title.id'))  # 关联外键title.id


class Add(db.Model):
    """记录未被收纳的搜索信息"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job = db.Column(db.String(), unique=True)  # 职位
    times = db.Column(db.Integer, default=0)  # 搜索次数


def create_default_admin(user_obj=None):
    """创建或恢复默认管理员"""
    if not user_obj:
        params = dict(name='admin', password='123456', is_admin=True)
        super_user = User(**params)
        db.session.add(super_user)
        print("初始化超级管理员成功！\n超级管理员账号名:admin  密码:123456 ")
    else:
        user_obj.name = 'admin'
        user_obj.password = '123456'
        user_obj.is_admin = True
        print("重置超级管理员成功！请谨慎更改超级管理员信息！\n"
              "超级管理员账号名:admin  密码:123456 ")
    db.session.commit()
    print("请通过登录host/login，登录成功后选择User表更改密码！请勿更改此账号名！")


# os.remove(path)# 删除数据库文件
# db.drop_all()  # 删除数据库
if not os.path.exists(path):  # 数据库不存在时才创建
    # 创建表
    db.create_all()
    # 创建默认管理员
    create_default_admin()

admin_verify = User.query.filter(User.name == 'admin').first()
if not admin_verify or not admin_verify.is_admin:  # 初始管理员被误删除
    # 或被设置为非管理员时，重启服务重新添加
    create_default_admin(admin_verify)

app = Flask(__name__)
app.secret_key = '33333333333333'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.login_message = '欢迎来到就业信息系统!请先完成登录！'
login_manager.init_app(app)


class MyModelView(ModelView):
    """重写ModelView方法，管理员用户可见编辑权限"""

    def is_accessible(self):  # 如果已登录且为管理员就返回True,否返回False
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.index', next=request.url))


# 管理员页面
admin = Admin(app)
admin.add_view(MyModelView(User, db.session))
admin.add_view(MyModelView(Title, db.session))
admin.add_view(MyModelView(Job, db.session))
admin.add_view(MyModelView(Add, db.session))


def response(message, status_code):
    return {
        'statusCode': str(status_code),
        'body': json.dumps(message),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
    }


@login_manager.user_loader
def load_user(user_id):
    ins = User.query.filter(User.id == user_id).first()
    if ins is not None:
        curr_user = User()
        curr_user.id = ins.id
        curr_user.is_admin = ins.is_admin
        return curr_user


@app.route('/')
def index():
    return render_template('index.html', ip=IP, title_list=TITLE_LIST)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form['password']
        ins = User.query.filter(User.name == username,
                                User.password == password).first()
        if ins is not None:
            curr_user = User()
            curr_user.id = ins.id
            login_user(curr_user)  # 通过Flask-Login的login_user方法登录用户
            if ins.is_admin:  # 是否为管理员
                return redirect(url_for('admin.index'))
            else:
                return render_template('index.html', ip=IP, title_list=TITLE_LIST)
        flash('用户名或密码错误!', 'error')
    flash('欢迎来到就业信息系统!请先完成登录!')  # GET 请求
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('退出成功！')
    return render_template('login.html')


@app.route('/search/<job_info>', methods=['GET'])
def search(job_info: str):
    """
    :param job_info: 格式:开发工程师(JAVA)
    :return:
    """
    job, title = __get_job_title(job_info)
    title_obj = Title.query.filter(Title.title == title).first()
    if title_obj:  # 每检索一次表中对于行的times+1
        if not title_obj.times:  # 初始值为null
            title_obj.times = 1
        else:
            title_obj.times += 1
        job_obj = Job.query.filter(Job.job == job
                                   and Job.title_id == title_obj.id).first()
        if not job_obj.times:
            job_obj.times = 1
        else:
            job_obj.times += 1
        try:
            db.session.commit()
        except Exception as e:
            _ = e
            db.session.rollback()
        return jsonify(status=1, job_title=title, img_name=NAME_LIST)
    else:
        time.sleep(random.randrange(1500, 2500) / 1000)
        return jsonify(status=0)


@app.route('/add/<job_info>', methods=['GET'])
def add_job(job_info: str):
    """
    :param job_info:
    :return:
    """
    job_info = __get_add_job(job_info)
    if not job_info:
        return jsonify(status=0)
    add_obj = Add.query.filter(Add.job == job_info).first()
    if not add_obj:  # 每检索一次表中对于行的times+1
        db.session.add(Add(job=job_info))
        add_obj = Add.query.filter(Add.job == job_info).first()
    if not add_obj.times:  # 初始值为null
        add_obj.times = 1
    else:
        add_obj.times += 1
    try:
        db.session.commit()
    except Exception as e:
        _ = e
        db.session.rollback()
        return jsonify(status=0)
    return jsonify(status=1)


@app.route('/refresh_job/', methods=['GET'])
def refresh_job():
    """仅限登录状态的管理员访问"""
    if current_user.is_authenticated and current_user.is_admin:
        __refresh_title_list()
        return jsonify(status=1, message='Refresh succeeded!')
    return jsonify(status=0, message='Refresh failed!',
                   error='Access is limited to logged in administrators')


@app.route('/analysis/<title>', methods=['GET'])
def analysis(title):
    """仅限登录状态的管理员访问"""
    if current_user.is_authenticated and current_user.is_admin:
        spider_51job.start(title)
        job_view_api.View(title)
        __refresh_title_list()
        return jsonify(status=1, message='Succeeded!')
    return jsonify(status=0, message='Failed!',
                   error='Access is limited to logged in administrators')


def __get_job_title(job_info):
    """切分出job和title"""
    job_info = job_info.replace('.,.', '/').replace('_,_', '\\')
    for i, s in enumerate(job_info[::-1], start=1):
        if s == '(':
            return job_info[:-i], job_info[-i + 1:-1]


def __get_add_job(job_info):
    """返回转换后的job_info"""
    job_info = job_info.replace('.,.', '/').replace('_,_', '\\') \
        .replace('"', '').replace("'", '').replace(' ', '')
    if job_info not in INVALID_DATA:  # 有效数据返回job_info
        return job_info


def __refresh_title_list():
    global TITLE_LIST
    TITLE_LIST = [f'{job_obj.job}({job_obj.title.title})' for job_obj in Job.query.filter().all() if
                  job_obj.title]


def flash_data():
    flush_host_ip()
    print(f'业务ip：{IP}')
    print(f'主页面：http://{IP}/')
    print(f'管理员页面：http://{IP}/admin')
    print(f'登录页面：http://{IP}/login')
    print(f'注销api：http://{IP}/logout')
    print(f'刷新职位api：http://{IP}/refresh_job')
    print(f'添加职位api：http://{IP}/analysis')
    while True:  # 每隔一小时刷新TITLE_LIST
        __refresh_title_list()
        time.sleep(60 * 60)


def flush_host_ip(ip=None):
    """该函数传入ip时使用该ip，否则自动获取"""
    global IP
    if ip:  # 手动设置ip
        IP = ip
        return

    for ip in socket.gethostbyname_ex(socket.gethostname())[-1][::-1]:  # type:str
        if 1 < int(ip.split('.')[3]) < 255:  # 过滤网络地址、主机地址、广播地址
            IP = ip
            return


# 初始化，存储所有可视化图表后缀名
NAME_LIST = ["_edu_salary_chart.png", "_area_top10_nums.png", "_area_top10_salary.png", "_job_top10_re.png",
             "_job_top6_salary.png", "_experience_edu_salary_chart.png", "_salary_proportion.png", "_WordCloud.jpg"]

# 主机IP：127.0.0.1 为默认ip
IP = '127.0.0.1'

# 定义无效数据
INVALID_DATA = {'', ' ', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'}

threading.Thread(target=flash_data, args=()).start()

if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=80)  # 多线程
