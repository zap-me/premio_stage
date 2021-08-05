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

from app_core import db
from models import User, Proposal, Payment, PayDbTransaction
import utils
from web_utils import bad_request, get_json_params
import web_utils
import paydb_core

logger = logging.getLogger(__name__)
reporting = Blueprint('reporting', __name__, template_folder='templates/reporting')

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

#@reporting.route('/report1')
def report_dashboard(premio_balance, premio_stage_account, total_balance):
    #### Dates
    ##
    #today = date.today()
    #yesterday = today - timedelta(days=1)
    #tomorrow = today + timedelta(days=1)
    #weekday = today.weekday()
    #monday = today - timedelta(days=weekday)
    #sunday = today + timedelta(days=(6 - weekday))
    #next_monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)
    #first_day_current_month = today.replace(day=1)
    #first_day_next_month = first_day_current_month + relativedelta(months=+1)
    #last_day_current_month = first_day_next_month - timedelta(days=1)
    #first_day_current_year = first_day_current_month + relativedelta(month=1)
    #first_day_next_year = first_day_current_year + relativedelta(years=+1)
    #last_day_current_year = first_day_next_year - timedelta(days=1)
    #### User queries
    ##
    #user_count = User.query.count()
    #user_result = User.query.order_by(User.confirmed_at).all()
    #user_count_today = user_counting(User, today, tomorrow)
    #user_count_yesterday = user_counting(User, yesterday, today)
    #user_count_weekly = user_counting(User, monday, next_monday)
    #user_count_monthly = user_counting(User, first_day_current_month, first_day_next_month)
    #user_count_yearly = user_counting(User, first_day_current_year, first_day_next_year)
    ### Proposal queries
    #
    proposal_count = Proposal.query.count()
    proposal_count_today = proposal_counting(Proposal, today, tomorrow)
    proposal_count_yesterday = proposal_counting(Proposal, yesterday, today)
    proposal_count_weekly = proposal_counting(Proposal,monday, next_monday)
    proposal_count_monthly = proposal_counting(Proposal, first_day_current_month, first_day_next_month)
    proposal_count_yearly = proposal_counting(Proposal, first_day_current_year, first_day_next_year)
    ### proposal/payment queries
    #
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
    premio_tx_count_today = premio_transaction_count(today, tomorrow)
    premio_tx_count_yesterday = premio_transaction_count(yesterday, today)
    premio_tx_count_week = premio_transaction_count(monday, next_monday)
    premio_tx_count_month = premio_transaction_count(first_day_current_month, first_day_next_month)
    premio_tx_count_year = premio_transaction_count(first_day_current_year, first_day_next_year)
    #print(premio_tx_count_lifetime)
    ### render template with the value
    return render_template('reporting/dashboard_paydb.html', premio_balance=premio_balance, premio_stage_account=premio_stage_account, total_balance=total_balance, \
#        user_result=user_result, user_count_today=user_count_today, user_count_yesterday=user_count_yesterday, \
#        user_count_weekly=user_count_weekly, user_count_monthly=user_count_monthly, user_count_yearly=user_count_yearly, user_count_lifetime=user_count, \
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

#@reporting.route('/report2')
def report_user_balance():
    users = User.query.all()
    ### User queries
    #
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

#@reporting.route('/report3')
def report_premio_txs(frequency):
    #today = date.today()
    #yesterday = today - timedelta(days=1)
    #tomorrow = today + timedelta(days=1)
    #weekday = today.weekday()
    #monday = today - timedelta(days=weekday)
    #sunday = today + timedelta(days=(6 - weekday))
    #next_monday = today + datetime.timedelta(days=-today.weekday(), weeks=1)
    #first_day_current_month = today.replace(day=1)
    #first_day_next_month = first_day_current_month + relativedelta(months=+1)
    #last_day_current_month = first_day_next_month - timedelta(days=1)
    #first_day_current_year = first_day_current_month + relativedelta(month=1)
    #first_day_next_year = first_day_current_year + relativedelta(years=+1)
    #last_day_current_year = first_day_next_year - timedelta(days=1)
    if frequency == 'lifetime':
        results = PayDbTransaction.query.join(User, \
                PayDbTransaction.sender_token == User.token).all()
    elif frequency == 'today':
        results = tx_paydbtransaction(today, tomorrow)
    elif frequency == 'yesterday':
        results = tx_paydbtransaction(yesterday, today)
    elif frequency == 'week':
        results = tx_paydbtransaction(monday, next_monday)
    elif frequency == 'month':
        results = tx_paydbtransaction(first_day_current_month, first_day_next_month)
    elif frequency == 'year':
        results = tx_paydbtransaction(first_day_current_year, first_day_next_year)
    if results:
        result_dict = []
        for result in results:
            result_dict.append(result.to_json())
        for result in result_dict:
            result['sender'] = result['sender'].split("@", 1)[0]
            result['recipient'] = result['recipient'].split("@", 1)[0]
            result['date'] = result['date'].split(" ", 1)[0]
            result['amount'] = utils.int2asset(result['amount'])
        #print(results)
        return render_template("reporting/dashboard_premio_transactions.html", result_dict=result_dict)
    return render_template("reporting/dashboard_premio_transactions.html")
    #if frequency == 'lifetime':
    #    results = Proposal.query.join(Payment, Payment.proposal_id == Proposal.id).all()
    #elif frequency == 'today':
    #    results = tx_proposals(today, tomorrow)
    #elif frequency == 'yesterday':
    #    results = tx_proposals(yesterday, today)
    #elif frequency == 'week':
    #    results = tx_proposals(monday, next_monday)
    #elif frequency == 'month':
    #    results = tx_proposals(first_day_current_month, first_day_next_month)
    #elif frequency == 'year':
    #    results = tx_proposals(first_day_current_year, first_day_next_year)
   # 
    #if results:
    #    result_dict = []
    #    for result in results:
    #        result['proposed_by'] = User.query.filter(User.id==result.proposer_id)
    #        result_dict.append(result)
    #    print(result_dict)
    #    #print(results)
    #    #return render_template("dashboad_proposal_txs.html", result_dict=result_dict)
    ##return render_template("dashboad_proposal_txs.html")

def report_proposal_txs(frequency):
    if frequency == 'lifetime':
        results = Proposal.query.join(Payment, Payment.proposal_id == Proposal.id)\
                .filter(and_(Proposal.date_authorized >= str(start_date),\
                Proposal.date_authorized < str(end_date))).all()
    elif frequency == 'today':
        results = tx_proposals(today, tomorrow)
    elif frequency == 'yesterday':
        results = tx_proposals(yesterday, today)
    elif frequency == 'week':
        results = tx_proposals(monday, next_monday)
    elif frequency == 'month':
        results = tx_proposals(first_day_current_month, first_day_next_month)
    elif frequency == 'year':
        results = tx_proposals(first_day_current_year, first_day_next_year)
    result_dict = []
    #print(result_dict)
    for result in results:
        #rec_date = result.date
        #rec_proposer_id = result.proposer_id
        #rec_


        return render_template("proposal_transaction.html", results=results)
    return 'ok'

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

def proposal_counting(table, start_date, end_date):
    result = table.query.filter(and_(table.date_authorized >= str(start_date), table.date_authorized < str(end_date))).count()
    if not result:
        result = 0
    return result

def user_counting(table, start_date, end_date):
    result = table.query.filter(and_(table.confirmed_at >= str(start_date), table.confirmed_at <= str(end_date))).count()
    if not result:
        result = 0
    return result

def tx_paydbtransaction(start_date, end_date):
    result = PayDbTransaction.query.join(User, PayDbTransaction.sender_token == User.token)\
            .filter(and_(PayDbTransaction.date >= str(start_date),\
            PayDbTransaction.date < str(end_date))).all()
    return result

def premio_transaction_count(start_date, end_date):
    result = PayDbTransaction.query.filter(PayDbTransaction.date >= str(start_date),\
            PayDbTransaction.date < str(end_date)).count()
    return result

def tx_proposals(start_date, end_date):
    result = Proposal.query.join(Payment, Payment.proposal_id == Proposal.id)\
            .filter(and_(Proposal.date_authorized >= str(start_date),\
            Proposal.date_authorized < str(end_date))).all()
    return result

