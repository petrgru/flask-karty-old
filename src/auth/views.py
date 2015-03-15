from flask import (Blueprint, escape, flash, render_template,
                   redirect, request, url_for,jsonify)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func,asc
from sqlalchemy.types import DateTime
from .forms import ResetPasswordForm, EmailForm, LoginForm, RegistrationForm,EditUserForm,username_is_available,email_is_available,Editdate
from ..data.database import db
from ..data.models import User, UserPasswordToken,Card
from ..data.util import generate_random_token
from ..decorators import reset_token_required
from ..emails import send_activation, send_password_reset
from ..extensions import login_manager
import simplejson as json
from collections import namedtuple
from datetime import datetime,timedelta

def last_day_of_month(year, month):
        """ Work out the last day of the month """
        last_days = [31, 30, 29, 28, 27]
        for i in last_days:
                try:
                        end = datetime(year, month, i)
                except ValueError:
                        continue
                else:
                        return end.day
        return None


blueprint = Blueprint('auth', __name__)

@blueprint.route('/activate', methods=['GET'])
def activate():
    " Activation link for email verification "
    userid = request.args.get('userid')
    activate_token = request.args.get('activate_token')

    user = db.session.query(User).get(int(userid)) if userid else None
    if user and user.is_verified():
        flash("Your account is already verified.", 'info')
    elif user and user.activate_token == activate_token:
        user.update(verified=True)
        flash("Thank you for verifying your email. Your account is now activated", 'info')
        return redirect(url_for('public.index'))
    else:
        flash("Invalid userid/token combination", 'warning')

    return redirect(url_for('public.index'))

@blueprint.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = EmailForm()
    if form.validate_on_submit():
        user = User.find_by_email(form.email.data)
        if user:
            reset_value = UserPasswordToken.get_or_create_token(user.id).value
            send_password_reset(user, reset_value)
            flash("Passowrd reset instructions have been sent to {}. Please check your inbox".format(user.email),
                  'info')
            return redirect(url_for("public.index"))
        else:
            flash("We couldn't find an account with that email. Please try again", 'warning')
    return render_template("auth/forgot_password.tmpl", form=form)

@login_manager.user_loader
def load_user(userid):  # pylint: disable=W0612
    "Register callback for loading users from session"
    return db.session.query(User).get(int(userid))

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.find_by_email(form.email.data)
        if user and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            flash("Logged in successfully", "info")
            return redirect(request.args.get('next') or url_for('public.index'))
        else:
            flash("Invalid email/password combination", "danger")
    return render_template("auth/login.tmpl", form=form)

@blueprint.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "info")
    return redirect(url_for('public.index'))

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        new_user = User.create(**form.data)
        login_user(new_user)
        send_activation(new_user)
        flash("Thanks for signing up {}. Welcome!".format(escape(new_user.username)), 'info')
        return redirect(url_for('public.index'))
    return render_template("auth/register.tmpl", form=form)


@blueprint.route('/resend_activation_email', methods=['GET'])
@login_required
def resend_activation_email():
    if current_user.is_verified():
        flash("This account has already been activated.", 'warning')
    else:
        current_user.update(activate_token=generate_random_token())
        send_activation(current_user)
        flash('Activation email sent! Please check your inbox', 'info')

    return redirect(url_for('public.index'))

@blueprint.route('/reset_password', methods=['GET', 'POST'])
@reset_token_required
def reset_password(userid, user_token):
    user = db.session.query(User).get(userid)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.update(password=form.password.data)
        user_token.update(used=True)
        flash("Password updated! Please log in to your account", "info")
        return redirect(url_for('public.index'))
    return render_template("auth/reset_password.tmpl", form=form)
@blueprint.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = db.session.query(User).get(current_user.id)
    form = EditUserForm(obj = user)
    if form.validate_on_submit():
        if form.username.data <> current_user.username :
            if not username_is_available(form.username.data):
                flash("Username is not allowed use another", "warning")
                return render_template("auth/EditAccount.tmpl", form=form)
        if form.email.data <> current_user.email:
            if not email_is_available(form.email.data):
                flash("Email is used use another email", "warning")
                return render_template("auth/EditAccount.tmpl", form=form)
        new_user = user.update(**form.data)
        login_user(new_user)
        flash("Saved successfully", "info")
        return redirect(request.args.get('next') or url_for('public.index'))

    return render_template("auth/EditAccount.tmpl", form=form)

@blueprint.route('/vypisy', methods=['GET'])
@login_required
def vypisy():

    #form=Card.find_by_number(current_user.card_number)
    #form = db.session.query(Card.time).filter_by(card_number=current_user.card_number)
    form = db.session.query( func.strftime('%Y-%m', Card.time).label("time")).filter_by(card_number=current_user.card_number).group_by(func.strftime('%Y-%m', Card.time))
        #.group_by([func.day(Card.time)])
    return render_template("auth/vypisy.tmpl", form=form)
@blueprint.route('/mesicni_vypis/<string:mesic>', methods=['GET'])
@login_required
def mesicni_vypis(mesic):

    #form=Card.find_by_number(current_user.card_number)
    #form = db.session.query(Card.time).filter_by(card_number=current_user.card_number)
    form = db.session.query( func.strftime('%Y-%m-%d', Card.time).label("date"),func.max(func.strftime('%H:%M', Card.time)).label("Max"),\
                             func.min(func.strftime('%H:%M', Card.time)).label("Min"),( func.max(Card.time) - func.min(Card.time)).label("Rozdil"))\
        .filter((func.strftime('%Y-%m', Card.time) == mesic) and (Card.card_number == current_user.card_number)).group_by(func.strftime('%Y-%m-%d', Card.time))
        #.group_by([func.day(Card.time)])
    return render_template("auth/mesicni_vypisy.tmpl", form=form)


from collections import OrderedDict
class DictSerializable(object):
    def _asdict(self):
        result = OrderedDict()
        for key in self.__mapper__.c.keys():
            result[key] = getattr(self, key)
        return result

@blueprint.route('/tbl_isdata/<int:od>/<int:do>', methods=['GET'])
@login_required
def tbl_insdata(od , do ):
    #data = db.session.query( func.strftime('%Y-%m', Card.time).label("time")).filter_by(card_number=current_user.card_number).group_by(func.strftime('%Y-%m', Card.time))
    if od==0 and do == 0 :
        data=db.session.query(Card.id,Card.card_number,func.strftime('%Y-%m', Card.time).label("time")).all()
    else:
        data=db.session.query(Card.id,Card.card_number,func.strftime('%Y-%m', Card.time).label("time")).slice(od,do)
    pole=['id','time','card_number']
    result = [{col: getattr(d, col) for col in pole} for d in data]
    return jsonify(data = result)




@blueprint.route('/tabletest', methods=['GET'])
@login_required
def tabletest():
    return render_template('public/table.tmpl')

@blueprint.route('/caljsonr/<int:card_number>/<int:year>/<int:mount>', methods=['GET'])
@login_required
def caljson_edit(card_number,year,mount):
    lastday = last_day_of_month(year , mount)
    data=[]
    startdate='8:00'
    enddate='16:00'
    for day in xrange(1,lastday):
        d = {}
        d['card_number']=card_number
        d['day']=day
        d['startdate']=startdate
        d['enddate']=enddate
        data.append(d)
    #print json.dumps(data, separators=(',',':'))

    #pole=['card_number','day','startdate','enddate']
    #result = [{col: d[col] for col in pole} for d in data]
    #print jsonify(data=result)



    #return render_template('auth/calendar.tmpl')
    return jsonify(data=data)

@blueprint.route('/calendar/<int:card_number>/<int:year>/<int:mounth>', methods=['GET'])
@login_required
def calendar(card_number,year,mounth):
    lastday = last_day_of_month(year , mounth)

    datarow=[]
    data={}
    startdate='8:00'
    enddate='16:00'
    data['stravenka']=0
    for day in xrange(1,lastday):
        d = {}
        d['day']=day
        d['dow']= datetime(year, mounth, day).weekday()
        if d['dow'] > 4:
            d['startdate']=''
            d['enddate']=''
        else:
            fromdate=datetime(year, mounth, day)
            todate=datetime(year, mounth, day) + timedelta(days=1)

            hodnota = db.session.query( func.min(func.strftime('%H:%M', Card.time)).label("Min")).filter(Card.time >= fromdate).filter(Card.time < todate).filter(Card.card_number == card_number)
                           #.group_by(func.strftime('%Y-%m-%d', Card.time)))
#            if len(hodnota) > 0 :
 #               print len(hodnota)

            d['startdate']=startdate
            d['enddate']=enddate
            rozdil=datetime.strptime(enddate,"%H:%M")-datetime.strptime(startdate,"%H:%M")
            d['timespend']=rozdil.total_seconds() / 3600
            if d['timespend'] >= 3:
                data['stravenka'] = data['stravenka'] + 1

        datarow.append(d)
    data['user']=current_user.email
    data['mounth']=mounth
    data['year']=year
    data['card_number']=card_number
    data['data']=datarow


    return render_template('auth/mesicni_vypis.tmpl',data=data)

@blueprint.route('/calendar_edit/<int:card_number>/<int:year>/<int:mounth>/<int:day>', methods=['GET','POST'])
@login_required
def calendar_edit(card_number,year,mounth,day):
    form = Editdate()
    form.den = str(day)  + '-' +  str(mounth)  +  '-' + str(year)
    form.card_number = str (card_number)
    if form.validate_on_submit():
        enddate=str(form.data['enddate'])
        flash("Saved successfully", "info")
        return redirect('calendar/'+str (card_number)+'/'+str(mounth)+'/'+str(day))
    return render_template('auth/editdate.tmpl', form=form)

