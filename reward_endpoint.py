# pylint: disable=unbalanced-tuple-unpacking

import logging
import time

from flask import Blueprint, request, jsonify

import web_utils
from web_utils import bad_request, get_json_params, request_get_signature, check_auth, auth_request, auth_request_get_single_param
import utils
from app_core import db, limiter
from models import User, Role, Category, Proposal, Payment, Referral

logger = logging.getLogger(__name__)
reward = Blueprint('reward', __name__, template_folder='templates')
limiter.limit("100/minute")(reward)

#
# Private (reward) API
#

@reward.route("/reward_create", methods=["POST"])
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

@reward.route('/referral_create', methods=['POST'])
def referral_create():
    recipient, api_key, err_response = auth_request_get_single_param(db, "recipient")
    if err_response:
        return err_response
    if not utils.is_email(recipient):
        return bad_request(web_utils.INVALID_EMAIL)
    recipient = recipient.lower()
    user = User.from_email(db.session, recipient)
    if user:
        time.sleep(5)
        return bad_request(web_utils.USER_EXISTS)
    #TODO: allow customisable referral params
    ref_reward_sender_type = Referral.REWARD_TYPE_FIXED
    ref_reward_sender = 1000
    ref_reward_recipient_type = Referral.REWARD_TYPE_FIXED
    ref_reward_recipient = 1000
    ref_recipient_min_spend = 5000
    ref = Referral(api_key.user, recipient, ref_reward_sender_type, ref_reward_sender, ref_reward_recipient_type, ref_reward_recipient, ref_recipient_min_spend)
    utils.email_referral(logger, ref)
    db.session.add(ref)
    db.session.commit()
    return 'ok'

@reward.route('/referral_remind', methods=['POST'])
def referral_remind():
    token, api_key, err_response = auth_request_get_single_param(db, "token")
    if err_response:
        return err_response
    ref = Referral.from_token_user(db.session, token, api_key.user)
    if not ref:
        return bad_request(web_utils.NOT_FOUND)
    if ref.status != ref.STATUS_CREATED:
        return bad_request(web_utils.NOT_FOUND)
    utils.email_referral(logger, ref)
    return 'ok'

@reward.route('/referral_list', methods=['POST'])
def referral_list():
    api_key, err_response = auth_request(db)
    if err_response:
        return err_response
    refs = Referral.from_user(db.session, api_key.user)
    refs = [ref.to_json() for ref in ref]
    return jsonify(dict(referrals=refs))

@reward.route('/referral_validate', methods=['POST'])
def referral_validate():
    token, api_key, err_response = auth_request_get_single_param(db, "token")
    if err_response:
        return err_response
    if not api_key.user.has_role(Role.ROLE_ADMIN) and not api_key.user.has_role(Role.ROLE_REFERRAL_CLAIMER):
        return bad_request(web_utils.UNAUTHORIZED)
    ref = Referral.from_token(db.session, token)
    if not ref:
        return bad_request(web_utils.NOT_FOUND)
    if ref.status != ref.STATUS_CREATED:
        return bad_request(web_utils.NOT_FOUND)
    return jsonify(dict(referral=ref.to_json()))

@reward.route('/referral_claim', methods=['POST'])
def referral_claim():
    token, api_key, err_response = auth_request_get_single_param(db, "token")
    if err_response:
        return err_response
    if not api_key.user.has_role(Role.ROLE_ADMIN) and not api_key.user.has_role(Role.ROLE_REFERRAL_CLAIMER):
        return bad_request(web_utils.UNAUTHORIZED)
    ref = Referral.from_token(db.session, token)
    if not ref:
        return bad_request(web_utils.NOT_FOUND)
    if ref.status != ref.STATUS_CREATED:
        return bad_request(web_utils.NOT_FOUND)
    #TODO: send referral rewards
    ref.status = ref.STATUS_CLAIMED
    db.session.add(ref)
    db.session.commit()
    return jsonify(dict(referral=ref.to_json()))
