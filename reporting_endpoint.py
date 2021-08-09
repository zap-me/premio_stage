# pylint: disable=unbalanced-tuple-unpacking

import logging
import time
import datetime
from datetime import date, timedelta
from dateutil.relativedelta import *
from sqlalchemy import func, and_

from flask import Blueprint, render_template, request, jsonify, flash, redirect
from flask_admin import BaseView
from flask_security import roles_accepted, current_user
import requests

from app_core import db, app, SERVER_MODE_WAVES
from models import Role, User, Proposal, Payment, PayDbTransaction
import utils
from web_utils import bad_request, get_json_params
import web_utils
import paydb_core

logger = logging.getLogger(__name__)
reporting = Blueprint('reporting', __name__, template_folder='templates/reporting')

SERVER_MODE = app.config["SERVER_MODE"]
if SERVER_MODE == SERVER_MODE_WAVES:
    # wave specific config settings
    NODE_BASE_URL = app.config["NODE_BASE_URL"]
    ADDRESS = app.config["WALLET_ADDRESS"]
    ASSET_ID = app.config["ASSET_ID"]
    TESTNET = app.config["TESTNET"]

### FREQUECNY DATES USED
today = date.today()
yesterday = today - timedelta(days=1)
tomorrow = today + timedelta(days=1)
weekday = today.weekday()
monday = today - timedelta(days=weekday)
sunday = today + timedelta(days=(6 - weekday))
next_monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)
first_day_current_month = today.replace(day=1)
first_day_next_month = first_day_current_month + relativedelta(months=+1)
last_day_current_month = first_day_next_month - timedelta(days=1)
first_day_current_year = first_day_current_month + relativedelta(month=1)
first_day_next_year = first_day_current_year + relativedelta(years=+1)
last_day_current_year = first_day_next_year - timedelta(days=1)

def report_dashboard(premio_balance, premio_stage_account, total_balance):
    ### Proposal queries
    proposal_count = Proposal.query.count()
    proposal_count_today = transaction_count(Proposal, today, tomorrow)
    proposal_count_yesterday = transaction_count(Proposal, yesterday, today)
    proposal_count_weekly = transaction_count(Proposal,monday, next_monday)
    proposal_count_monthly = transaction_count(Proposal, first_day_current_month, first_day_next_month)
    proposal_count_yearly = transaction_count(Proposal, first_day_current_year, first_day_next_year)
    
    ### Payment queries
    payment_query_today = claimed_proposal_payment(Proposal, Payment, today, tomorrow)
    unclaimed_payment_query_today = unclaimed_proposal_payment(Proposal, Payment, today, tomorrow)
    total_payment_query_today = total_proposal_payment(Proposal, Payment, today, tomorrow)
    payment_query_yesterday = claimed_proposal_payment(Proposal, Payment, yesterday, today)
    unclaimed_payment_query_yesterday = unclaimed_proposal_payment(Proposal, Payment, yesterday, today)
    total_payment_query_yesterday = total_proposal_payment(Proposal, Payment, yesterday, today)
    payment_query_weekly = claimed_proposal_payment(Proposal, Payment, monday, next_monday)
    unclaimed_payment_query_weekly = unclaimed_proposal_payment(Proposal, Payment, monday, next_monday)
    total_payment_query_weekly = total_proposal_payment(Proposal, Payment, monday, next_monday)
    payment_query_monthly = claimed_proposal_payment(Proposal, Payment, first_day_current_month, first_day_next_month)
    unclaimed_payment_query_monthly = unclaimed_proposal_payment(Proposal, Payment, first_day_current_month, first_day_next_month)
    total_payment_query_monthly = total_proposal_payment(Proposal, Payment, first_day_current_month, first_day_next_month)
    payment_query_yearly = claimed_proposal_payment(Proposal, Payment, first_day_current_year, first_day_next_year)
    unclaimed_payment_query_yearly = unclaimed_proposal_payment(Proposal, Payment, first_day_current_year, first_day_next_year)
    total_payment_query_yearly = total_proposal_payment(Proposal, Payment, first_day_current_year, first_day_next_year)
    payment_query_lifetime = claimed_lifetime(Proposal, Payment)
    unclaimed_payment_query_lifetime = unclaimed_lifetime(Proposal, Payment)
    total_payment_query_lifetime = total_lifetime(Proposal, Payment)
    
    ### Premio (PayDbTransaction)
    premio_tx_count_lifetime = PayDbTransaction.query.count()
    premio_tx_count_today = transaction_count(PayDbTransaction, today, tomorrow)
    premio_tx_count_yesterday = transaction_count(PayDbTransaction, yesterday, today)
    premio_tx_count_week = transaction_count(PayDbTransaction, monday, next_monday)
    premio_tx_count_month = transaction_count(PayDbTransaction, first_day_current_month, first_day_next_month)
    premio_tx_count_year = transaction_count(PayDbTransaction, first_day_current_year, first_day_next_year)

    ### render template with the value
    return render_template('reporting/dashboard_paydb.html', premio_balance=premio_balance, premio_stage_account=premio_stage_account, total_balance=total_balance, \
        proposal_count_lifetime=proposal_count, proposal_count_today=proposal_count_today, proposal_count_yesterday=proposal_count_yesterday, \
        proposal_count_weekly=proposal_count_weekly, proposal_count_monthly=proposal_count_monthly, proposal_count_yearly=proposal_count_yearly, \
        payment_query_today=payment_query_today, unclaimed_payment_query_today=unclaimed_payment_query_today, total_payment_query_today=total_payment_query_today, \
        payment_query_yesterday=payment_query_yesterday, \
        unclaimed_payment_query_yesterday=unclaimed_payment_query_yesterday, payment_query_weekly=payment_query_weekly, \
        unclaimed_payment_query_weekly=unclaimed_payment_query_weekly, payment_query_monthly=payment_query_monthly, \
        unclaimed_payment_query_monthly=unclaimed_payment_query_monthly,payment_query_yearly=payment_query_yearly, \
        unclaimed_payment_query_yearly=unclaimed_payment_query_yearly,payment_query_lifetime=payment_query_lifetime, \
        unclaimed_payment_query_lifetime=unclaimed_payment_query_lifetime, \
        total_payment_query_yesterday=total_payment_query_yesterday,total_payment_query_weekly=total_payment_query_weekly, \
        total_payment_query_monthly=total_payment_query_monthly, total_payment_query_yearly=total_payment_query_yearly, \
        total_payment_query_lifetime=total_payment_query_lifetime, premio_tx_count_lifetime=premio_tx_count_lifetime, \
        premio_tx_count_today=premio_tx_count_today, premio_tx_count_yesterday=premio_tx_count_yesterday, \
        premio_tx_count_week=premio_tx_count_week, premio_tx_count_month=premio_tx_count_month, premio_tx_count_year=premio_tx_count_year)

def report_user_balance():
    ### User queries
    users = User.query.all()
    user_count = User.query.count()
    user_result = User.query.order_by(User.confirmed_at).all()
    user_count_today = user_counting(User, today, tomorrow)
    user_count_yesterday = user_counting(User, yesterday, today)
    user_count_weekly = user_counting(User, monday, next_monday)
    user_count_monthly = user_counting(User, first_day_current_month, first_day_next_month)
    user_count_yearly = user_counting(User, first_day_current_year, first_day_next_year)
    users_balances = []
    for account_user in users:
        user = User.from_email(db.session, account_user.email)
        if user:
            balance = paydb_core.user_balance_from_user(db.session, user)
            balance = utils.int2asset(balance)
            email_balance = {'user': user.email, 'balance': balance}
            users_balances.append(email_balance)
            sorted_users_balances = sorted(users_balances, key=lambda k:float(k['balance']), reverse=True)
    return render_template("reporting/dashboard_user_balance.html", user_count=user_count, users_balances=sorted_users_balances, user_count_today=user_count_today, user_count_yesterday=user_count_yesterday, user_count_weekly=user_count_weekly, user_count_monthly=user_count_monthly, user_count_yearly=user_count_yearly, user_count_lifetime=user_count)

def report_premio_txs(frequency):
    if frequency == 'lifetime':
        return redirect('/admin/paydbtransaction/')
    elif frequency == 'today':
        return redirect('/admin/paydbtransaction/?flt1_0='+str(today)+'+to+'+str(tomorrow))
    elif frequency == 'yesterday':
        return redirect('/admin/paydbtransaction/?flt1_0='+str(yesterday)+'+to+'+str(today))
    elif frequency == 'week':
        return redirect('/admin/paydbtransaction/?flt1_0='+str(monday)+'+to+'+str(next_monday))
    elif frequency == 'month':
        return redirect('/admin/paydbtransaction/?flt1_0='+str(first_day_current_month)+'+to+'+str(first_day_next_month))
    elif frequency == 'year':
        return redirect('/admin/paydbtransaction/?flt1_0='+str(first_day_current_year)+'+to+'+str(first_day_next_year))

def report_proposal_txs(frequency):
    if frequency == 'lifetime':
        return redirect('/admin/proposal')
    elif frequency == 'today':
        return redirect('/admin/proposal?flt0_0='+str(today)+'+to+'+str(tomorrow))
    elif frequency == 'yesterday':
        return redirect('/admin/proposal?flt0_0='+str(yesterday)+'+to+'+str(today))
    elif frequency == 'week':
        return redirect('/admin/proposal?flt0_0='+str(monday)+'+to+'+str(next_monday))
    elif frequency == 'month':
        return redirect('/admin/proposal?flt0_0='+str(first_day_current_month)+'+to+'+str(first_day_next_month))
    elif frequency == 'year':
        return redirect('/admin/proposal?flt0_0='+str(first_day_current_year)+'+to+'+str(first_day_next_year))
        
def claimed_proposal_payment(table1, table2, start_date, end_date):
    result = table1.query.join(table2, table1.id==table2.proposal_id)\
            .filter(and_(table1.date_authorized >= str(start_date),\
            table1.date_authorized < str(end_date))).filter(table2.status == 'sent_funds').with_entities(func.sum(table2.amount)).scalar()
    if not result:
        result = 0
    result = utils.int2asset(result)
    return result

def unclaimed_proposal_payment(table1, table2, start_date, end_date):
    result = table1.query.join(table2, table1.id==table2.proposal_id)\
            .filter(and_(table1.date_authorized >= str(start_date),\
            table1.date_authorized < str(end_date))).filter(table2.status != 'sent_funds').with_entities(func.sum(table2.amount)).scalar()
    if not result:
        result = 0
    result = utils.int2asset(result)
    return result

def total_proposal_payment(table1, table2, start_date, end_date):
    result = table1.query.join(table2, table1.id==table2.proposal_id)\
            .filter(and_(table1.date_authorized >= str(start_date),\
            table1.date_authorized < str(end_date))).with_entities(func.sum(table2.amount)).scalar()
    if not result:
        result = 0
    result = utils.int2asset(result)
    return result

def claimed_lifetime(table1, table2):
    result = table1.query.join(table2, table1.id==table2.proposal_id)\
            .filter(table2.status == 'sent_funds').with_entities(func.sum(table2.amount)).scalar()
    if not result:
        result = 0
    result = utils.int2asset(result)
    return result

def unclaimed_lifetime(table1, table2):
    result = table1.query.join(table2, table1.id==table2.proposal_id)\
            .filter(table2.status != 'sent_funds').with_entities(func.sum(table2.amount)).scalar()
    if not result:
        result = 0
    result = utils.int2asset(result)
    return result

def total_lifetime(table1, table2):
    result = table1.query.join(table2, table1.id==table2.proposal_id)\
            .with_entities(func.sum(table2.amount)).scalar()
    if not result:
        result = 0
    result = utils.int2asset(result)
    return result

def user_counting(table, start_date, end_date):
    result = table.query.filter(and_(table.confirmed_at >= str(start_date), table.confirmed_at <= str(end_date))).count()
    if not result:
        result = 0
    return result

def transaction_count(table, start_date, end_date):
    result = table.query.filter(and_(table.date >= str(start_date), table.date < str(end_date))).count()
    if not result:
        result = 0
    return result

def from_int_to_user_friendly(val, divisor, decimal_places=4):
    if not isinstance(val, int):
        return val
    val = val / divisor
    return round(val, decimal_places)


def dashboard_data_waves():
    # get balance of local wallet
    url = NODE_BASE_URL + f"/assets/balance/{ADDRESS}/{ASSET_ID}"
    logger.info("requesting %s..", url)
    response = requests.get(url)
    try:
        asset_balance = response.json()["balance"]
    except: # pylint: disable=bare-except
        logger.error("failed to parse response")
        asset_balance = "n/a"
    url = NODE_BASE_URL + f"/addresses/balance/{ADDRESS}"
    logger.info("requesting %s..", url)
    response = requests.get(url)
    try:
        waves_balance = response.json()["balance"]
    except: # pylint: disable=bare-except
        logger.error("failed to parse response")
        waves_balance = "n/a"
    # get the balance of the main wallet
    url = NODE_BASE_URL + f"/transactions/info/{ASSET_ID}"
    logger.info("requesting %s..", url)
    response = requests.get(url)
    try:
        issuer = response.json()["sender"]
        url = NODE_BASE_URL + f"/assets/balance/{issuer}/{ASSET_ID}"
        logger.info("requesting %s..", url)
        response = requests.get(url)
        master_asset_balance = response.json()["balance"]
        url = NODE_BASE_URL + f"/addresses/balance/{issuer}"
        logger.info("requesting %s..", url)
        response = requests.get(url)
        master_waves_balance = response.json()["balance"]
    except: # pylint: disable=bare-except
        logger.error("failed to parse response")
        issuer = "n/a"
        master_waves_balance = "n/a"
        master_asset_balance = "n/a"
    # return data
    return {"asset_balance": asset_balance, "asset_address": ADDRESS, "waves_balance": waves_balance, \
            "master_asset_balance": master_asset_balance, "master_waves_balance": master_waves_balance, "master_waves_address": issuer, \
            "asset_id": ASSET_ID, \
            "testnet": TESTNET, \
            "premio_qrcode": utils.qrcode_svg_create(ADDRESS), \
            "issuer_qrcode": utils.qrcode_svg_create(issuer), \
            "wavesexplorer": app.config["WAVESEXPLORER"]}

def dashboard_data_paydb():
    premio_stage_balance = -1
    premio_stage_account = app.config['OPERATIONS_ACCOUNT']
    user = User.from_email(db.session, premio_stage_account)
    if user:
        premio_stage_balance = paydb_core.user_balance_from_user(db.session, user)
    total_balance = paydb_core.balance_total(db.session)
    # return data
    return {"premio_stage_balance": premio_stage_balance, "premio_stage_account": premio_stage_account, \
            "total_balance": total_balance}

@reporting.route("/dashboard")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard():
    if SERVER_MODE == SERVER_MODE_WAVES:
        data = dashboard_data_waves()
        data["asset_balance"] = utils.int2asset(data["asset_balance"])
        data["waves_balance"] = from_int_to_user_friendly(data["waves_balance"], 10**8)
        data["master_asset_balance"] = utils.int2asset(data["master_asset_balance"])
        data["master_waves_balance"] = from_int_to_user_friendly(data["master_waves_balance"], 10**8)
        return render_template("reporting/dashboard_waves.html", data=data)
    data = dashboard_data_paydb()
    data["premio_stage_balance"] = utils.int2asset(data["premio_stage_balance"])
    data["total_balance"] = utils.int2asset(data["total_balance"])
    return report_dashboard(data["premio_stage_balance"], data["premio_stage_account"], data["total_balance"])

@reporting.route("/dashboard_report")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_report():
    if SERVER_MODE == SERVER_MODE_WAVES:
        data = dashboard_data_waves()
        data["asset_balance"] = utils.int2asset(data["asset_balance"])
        data["waves_balance"] = from_int_to_user_friendly(data["waves_balance"], 10**8)
        data["master_asset_balance"] = utils.int2asset(data["master_asset_balance"])
        data["master_waves_balance"] = from_int_to_user_friendly(data["master_waves_balance"], 10**8)
        return render_template("reporting/dashboard_waves.html", data=data)
    data = dashboard_data_paydb()
    data["premio_stage_balance"] = utils.int2asset(data["premio_stage_balance"])
    data["total_balance"] = utils.int2asset(data["total_balance"])
    return report_dashboard(data["premio_stage_balance"], data["premio_stage_account"], data["total_balance"])

### List username with their balances
@reporting.route("/dashboard_user_balance")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_user_balance():
    return report_user_balance()

### Premio Txs Dashboard
@reporting.route("/dashboard_premio_tx_today")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_premio_tx_today():
    today = str('today')
    return report_premio_txs(today)

@reporting.route("/dashboard_premio_tx_yesterday")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_premio_tx_yesterday():
    yesterday = str('yesterday')
    return report_premio_txs(yesterday)

@reporting.route("/dashboard_premio_tx_week")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_premio_tx_week():
    week = str('week')
    return report_premio_txs(week)

@reporting.route("/dashboard_premio_tx_month")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_premio_tx_month():
    month = str('month')
    return report_premio_txs(month)

@reporting.route("/dashboard_premio_tx_year")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_premio_tx_year():
    year = str('year')
    return report_premio_txs(year)

@reporting.route("/dashboard_premio_tx_lifetime")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_premio_tx_lifetime():
    lifetime = str('lifetime')
    return report_premio_txs(lifetime)

### Proposal Dashboard:
@reporting.route("/dashboard_proposal_tx_today")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_proposal_tx_today():
    today = str('today')
    return report_proposal_txs(today)

@reporting.route("/dashboard_proposal_tx_yesterday")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_proposal_tx_yesterday():
    yesterday = str('yesterday')
    return report_proposal_txs(yesterday)

@reporting.route("/dashboard_proposal_tx_week")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_proposal_tx_week():
    week = str('week')
    return report_proposal_txs(week)

@reporting.route("/dashboard_proposal_tx_month")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_proposal_tx_month():
    month = str('month')
    return report_proposal_txs(month)

@reporting.route("/dashboard_proposal_tx_year")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_proposal_tx_year():
    year = str('year')
    return report_proposal_txs(year)

@reporting.route("/dashboard_proposal_tx_lifetime")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard_proposal_tx_lifetime():
    lifetime = str('lifetime')
    return report_proposal_txs(lifetime)