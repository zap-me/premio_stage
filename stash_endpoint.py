# pylint: disable=unbalanced-tuple-unpacking
# pylint: disable=invalid-name
# pylint: disable=unused-import

import logging
#import json
import time
import datetime

from flask import Blueprint, render_template, request, jsonify, flash, redirect

from app_core import app, db
from models import UserStash, UserStashRequest
import utils
from web_utils import bad_request, get_json_params
import web_utils

logger = logging.getLogger(__name__)
stash_bp = Blueprint('stash_bp', __name__, template_folder='templates')

@stash_bp.route('/save', methods=['POST'])
def stash_save():
    content = request.get_json(force=True)
    if content is None:
        return bad_request(web_utils.INVALID_JSON)
    params, err_response = get_json_params(content, ["key", "email", "IV", "cyphertext", "question"])
    if err_response:
        return err_response
    key, email, IV, cyphertext, question = params
    stash_req = UserStashRequest(key, email, IV, cyphertext, question, UserStashRequest.ACTION_CREATE)
    db.session.add(stash_req)
    db.session.commit()
    utils.email_stash_request(logger, email, stash_req, stash_req.MINUTES_EXPIRY)
    return jsonify(dict(token=stash_req.token))

@stash_bp.route('/save_check/<token>')
def stash_save_check(token=None):
    req = UserStashRequest.from_token(db.session, token)
    if not req:
        #return bad_request()
        flash('STASH token not exist.', 'danger')
        return redirect('/')
    #return jsonify(dict(confirmed=req.created_stash != None))
    return jsonify(dict(confirmed=req.created_stash is not None))

@stash_bp.route('/save_confirm/<token>/<secret>', methods=['GET', 'POST'])
def stash_save_confirm(token=None, secret=None):
    req = UserStashRequest.from_token(db.session, token)
    if not req:
        time.sleep(5)
        flash('STASH request not found.', 'danger')
        return redirect('/')
    now = datetime.datetime.now()
    if now > req.expiry:
        time.sleep(5)
        flash('STASH request expired.', 'danger')
        return redirect('/')
    if req.secret != secret:
        flash('STASH code invaid.', 'danger')
        return redirect('/')
    if request.method == 'POST':
        # pylint: disable=duplicate-code
        confirm = request.form.get('confirm') == 'true'
        if not confirm:
            db.session.delete(req)
            db.session.commit()
            flash('STASH cancelled.', 'success')
            return redirect('/')
        stash = UserStash(req)
        req.created_stash = stash
        db.session.add(req)
        db.session.add(stash)
        db.session.commit()
        flash('STASH confirmed.', 'success')
        return redirect('/')
    return render_template('stash/stash_confirm.html', req=req)

@stash_bp.route('/load/<email>/<key>', methods=['GET', 'POST'])
def stash_load(email, key):
    email_hash = utils.sha256(email)
    # pylint: disable=no-member
    req = db.session.query(UserStashRequest).\
        filter(UserStashRequest.email_hash == str(email_hash)).\
        filter(UserStashRequest.key == key).first()
    if not req:
        flash('STASH email and key not found.', 'danger')
        return redirect('/')
    utils.email_stash_loadrequest(logger, email, req, req.MINUTES_EXPIRY)
    flash("Please check you're email to confirm.", 'success')
    return redirect('/')

@stash_bp.route('/load_check/<email>/<key>')
def stash_load_check(email, key):
    email_hash = utils.sha256(email)
    req = UserStash.from_email_hash(db.session, email_hash, key)
    if not req:
        #return bad_request()
        flash('STASH token not exist.', 'danger')
        return redirect('/')
    return jsonify(dict(email_hash=req.email_hash, key=req.key, IV=req.IV, cyphertext=req.cyphertext, question=req.question))

@stash_bp.route('/load_confirm/<token>/<secret>', methods=['GET', 'POST'])
def stash_load_confirm(token, secret):
    # pylint: disable=no-member
    req = db.session.query(UserStashRequest).\
        filter(UserStashRequest.token == str(token)).first()
    if not req:
        flash('STASH token not exist.', 'danger')
        return redirect('/')
    if request.method == 'POST':
        confirm = request.form.get('confirm') == 'true'
        if not confirm:
            flash('STASH cancelled.', 'success')
            return redirect('/')
        flash('STASH confirmed.', 'success')
        return redirect('/')
    return render_template('stash/stash_load_confirm.html', req=req)
