# pylint: disable=unbalanced-tuple-unpacking

import logging
import time
import datetime
import json

from flask import Blueprint, request, jsonify, flash, redirect, render_template
import flask_security
from flask_security.utils import encrypt_password
from flask_socketio import Namespace, emit, join_room, leave_room

import web_utils
from web_utils import bad_request, get_json_params, request_get_signature, check_auth
import utils
from app_core import db, socketio
from models import user_datastore, User, Role, Category, Proposal, Payment, UserCreateRequest, UserUpdateEmailRequest, Permission, ApiKey, ApiKeyRequest, PayDbTransaction
import paydb_core

logger = logging.getLogger(__name__)
reward = Blueprint('reward', __name__, template_folder='templates')

#
# Private (reward) API
#

@app.route("/reward_create", methods=["POST"])
def reward_create():
    sig = request_get_signature()
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["api_key", "nonce", "reason", "category", "recipient", "amount", "message"])
    if err_response:
        return err_response
    api_key, nonce, reason, category, recipient, amount, message = params
    res, auth_fail_reason, api_key = check_auth(db.session, api_key, nonce, sig, request.data)
    if not res:
        return bad_request(auth_fail_reason)
    if not api_key.user.has_role(Role.ROLE_ADMIN) and not api_key.user.has_role(Role.ROLE_AUTHORIZER):
        return bad_request(web_utils.UNAUTHORIZED)
    cat = Category.from_name(db.session, category)
    if not cat:
        return bad_request(web_utils.INVALID_CATEGORY)
    proposal = Proposal(api_key.user, reason)
    proposal.categories.append(cat)
    proposal.authorize(api_key.user)
    db.session.add(proposal)
    email = recipient if utils.is_email(recipient) else None
    mobile = recipient if utils.is_mobile(recipient) else None
    address = recipient if utils.is_address(recipient) else None
    payment = Payment(proposal, mobile, email, address, message, amount)
    db.session.add(payment)
    db.session.commit()
    return jsonify(dict(proposal=dict(reason=reason, category=category, status=proposal.status, payment=dict(amount=amount, email=email, mobile=mobile, address=address, message=message, status=payment.status))))

@paydb.route('/referral_create', methods=['POST'])
def referral_create():
    sig = request_get_signature()
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["api_key", "nonce", "recipient"])
    if err_response:
        return err_response
    api_key, nonce, recipient = params
    res, reason, api_key = check_auth(db.session, api_key, nonce, sig, request.data)
    if not res:
        return bad_request(reason)
    if not utils.is_email(recipient):
        return bad_request(web_utils.INVALID_EMAIL)
    #TODO
    #recipient = recipient.lower()
    #ref = Referral(..)
    #utils.email_referral(logger, ref)
    #db.session.add(ref)
    #db.session.commit()
    #return 'ok'
    return bad_request(web_utils.NOT_IMPLEMENTED)

@paydb.route('/referral_remind', methods=['POST'])
def referral_remind():
    sig = request_get_signature()
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["api_key", "nonce", "token"])
    if err_response:
        return err_response
    api_key, nonce, token = params
    res, reason, api_key = check_auth(db.session, api_key, nonce, sig, request.data)
    if not res:
        return bad_request(reason)
    #TODO
    #ref = Referral.from_token_user(db.session, token, api_key.user)
    #if not ref:
    #    return bad_request(web_utils.NOT_FOUND)
    #if ref.status != ref.STATUS_CREATED:
    #    return bad_request(web_utils.NOT_FOUND)
    #utils.email_referral(logger, ref)
    #return 'ok'
    return bad_request(web_utils.NOT_IMPLEMENTED)

@paydb.route('/referral_list', methods=['POST'])
def referral_list():
    sig = request_get_signature()
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["api_key", "nonce"])
    if err_response:
        return err_response
    api_key, nonce = params
    res, reason, api_key = check_auth(db.session, api_key, nonce, sig, request.data)
    if not res:
        return bad_request(reason)
    #TODO
    #refs = Referral.from_user(db.session, api_key.user)
    #return jsonify(refs)
    return bad_request(web_utils.NOT_IMPLEMENTED)

@paydb.route('/referral_validate', methods=['POST'])
def referral_validate():
    sig = request_get_signature()
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["api_key", "nonce", "token"])
    if err_response:
        return err_response
    api_key, nonce, token = params
    res, reason, api_key = check_auth(db.session, api_key, nonce, sig, request.data)
    if not res:
        return bad_request(reason)
    if not api_key.user.has_role(Role.ROLE_ADMIN) and not api_key.user.has_role(Role.ROLE_REFERRAL_CLAIMER):
        return bad_request(web_utils.UNAUTHORIZED)
    #TODO
    #ref = Referral.from_token(db.session, token)
    #if not ref:
    #    return bad_request(web_utils.NOT_FOUND)
    #if ref.status != ref.STATUS_CREATED:
    #    return bad_request(web_utils.NOT_FOUND)
    #return jsonify(ref)
    return bad_request(web_utils.NOT_IMPLEMENTED)

@paydb.route('/referral_claim', methods=['POST'])
def referral_claim():
    sig = request_get_signature()
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["api_key", "nonce", "token"])
    if err_response:
        return err_response
    api_key, nonce, token = params
    res, reason, api_key = check_auth(db.session, api_key, nonce, sig, request.data)
    if not res:
        return bad_request(reason)
    if not api_key.user.has_role(Role.ROLE_ADMIN) and not api_key.user.has_role(Role.ROLE_REFERRAL_CLAIMER):
        return bad_request(web_utils.UNAUTHORIZED)
    #TODO
    #ref = Referral.from_token(db.session, token)
    #if not ref:
    #    return bad_request(web_utils.NOT_FOUND)
    #if ref.status != ref.STATUS_CREATED:
    #    return bad_request(web_utils.NOT_FOUND)
    #ref.status = ref.STATUS_CLAIMED
    #db.session.add(ref)
    #db.session.commit()
    #return jsonify(ref)
    return bad_request(web_utils.NOT_IMPLEMENTED)
