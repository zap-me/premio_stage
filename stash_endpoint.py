# pylint: disable=unbalanced-tuple-unpacking

import logging
import json
#import base64
import time
import datetime
#from urllib.parse import urlparse

from flask import Blueprint, render_template, request, jsonify, flash, redirect
#from flask_jsonrpc.exceptions import OtherError

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
        return bad_request()
    return jsonify(dict(confirmed=req.created_stash != None))

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
    ### create hash for the email
    email_hash = utils.sha256(email)
    ### check the email_hash and key is the same in the db.
    req = db.session.query(UserStashRequest).\
        filter(UserStashRequest.email_hash == str(email_hash)).\
        filter(UserStashRequest.key == key).first()
    if not req:
        flash('STASH email and key not found.', 'danger')
        return redirect('/')
    ### send email but its erroring#
    utils.email_stash_loadrequest(logger, email, req, req.MINUTES_EXPIRY)
    ### return the req
    flash('STASH email and key found', 'success')
    #return render_template('stash/stash_load.html', req=req)
    return redirect('/')

@stash_bp.route('/load_confirm/<token>/<secret>', methods=['GET', 'POST'])
def stash_load_confirm(token, secret):
    req = db.session.query(UserStashRequest).\
        filter(UserStashRequest.token == str(token)).first()
    if not req:
        flash('STASH token not exist.', 'danger')
        return redirect('/')
    return render_template('stash/stash_load_confirm.html', req=req)

### This testappears to work
@app.route('/test1')
def test1():
    #userstash_result = UserStash.query.all()
    #seed_words = Seeds.query.filter_by(user_id = current_user.id).first()
    #userstash_result = UserStash.query.filter(UserStash.email == 'eoliveros@redratclothing.co.nz').first()
    #seeds = session.query(Seeds).filter(Seeds.user_id == user.id).all()
    #userstash_result = db.session.query(UserStash).filter(UserStash.id == 'eoliveros@redratclothing.co.nz')
    #userstash_result = UserStash.query.all()
    #if userstash_result:
    #    return userstash_result
    #return 'Not found'
    #return UserStash.query.filter(UserStash.email == 'eoliveros@redratclothing.co.nz').first()
    email_hash = utils.sha256('e.f.oliveros@gmail.com')
    print(email_hash)
    userstashrequest_result = UserStashRequest.query.filter(UserStashRequest.email_hash == email_hash).first()
    if not userstashrequest_result:
        flash('STASH email not found', 'danger')
        return redirect('/')
    return render_template('stash/test.html')
    
## wave specific config settings
#NODE_BASE_URL = app.config["NODE_BASE_URL"]
#SEED = app.config["WALLET_SEED"]
#ADDRESS = app.config["WALLET_ADDRESS"]
#ASSET_ID = app.config["ASSET_ID"]
#ASSET_NAME = app.config["ASSET_NAME"]
#TESTNET = app.config["TESTNET"]
#TX_SIGNERS = app.config["TX_SIGNERS"]
#ASSET_MASTER_PUBKEY = app.config["ASSET_MASTER_PUBKEY"]
#
##
## Jinja2 filters
##
#
#@app.context_processor
#def inject_config_qrcode_svg():
#    url_parts = urlparse(request.url)
#    url = url_parts._replace(scheme="premiomwlink", path="/config").geturl()
#    qrcode_svg = utils.qrcode_svg_create(url, box_size=6)
#    return dict(mw_config_url=url, mw_config_qrcode_svg=qrcode_svg)
#
##
## Flask views
##
#
#@app.route("/config")
#def config():
#    return jsonify(dict(asset_id=ASSET_ID, asset_name=ASSET_NAME, testnet=TESTNET, tx_signers=TX_SIGNERS, tx_types=tx_utils.TYPES))
#
#@app.route("/tx_link/<txid>")
#def tx_link(txid):
#    url_parts = urlparse(request.url)
#    url = url_parts._replace(scheme="premiomwlink", path="/txid/" + txid).geturl()
#    qrcode_svg = utils.qrcode_svg_create(url)
#    return render_template("mw/tx_link.html", qrcode_svg=qrcode_svg, url=url)
#
#@app.route("/tx_create", methods=["POST"])
#def tx_create():
#    tx_utils.tx_init_chain_id(TESTNET)
#
#    content = request.get_json(force=True)
#    if content is None:
#        return bad_request("failed to decode JSON object")
#    params, err_response = get_json_params(content, ["type", "timestamp"])
#    if err_response:
#        return err_response
#    type_, timestamp = params
#    if not type_ in tx_utils.TYPES:
#        return bad_request("'type' not valid")
#    pubkey = ASSET_MASTER_PUBKEY
#    address = tx_utils.generate_address(pubkey)
#    amount = 0
#    if type_ == "transfer":
#        fee = tx_utils.get_fee(NODE_BASE_URL, tx_utils.DEFAULT_TX_FEE, address, None)
#        params, err_response = get_json_params(content, ["recipient", "amount"])
#        if err_response:
#            return err_response
#        recipient, amount = params
#        tx = tx_utils.transfer_asset_payload(address, pubkey, None, recipient, ASSET_ID, amount, "", None, fee, timestamp)
#    elif type_ == "issue":
#        fee = tx_utils.get_fee(NODE_BASE_URL, tx_utils.DEFAULT_ASSET_FEE, address, None)
#        params, err_response = get_json_params(content, ["asset_name", "asset_description", "amount"])
#        if err_response:
#            return err_response
#        asset_name, asset_description, amount = params
#        tx = tx_utils.issue_asset_payload(address, pubkey, None, asset_name, asset_description, amount, None, 2, True, fee, timestamp)
#    elif type_ == "reissue":
#        fee = tx_utils.get_fee(NODE_BASE_URL, tx_utils.DEFAULT_ASSET_FEE, address, None)
#        params, err_response = get_json_params(content, ["amount"])
#        if err_response:
#            return err_response
#        amount, = params
#        tx = tx_utils.reissue_asset_payload(address, pubkey, None, ASSET_ID, amount, True, fee, timestamp)
#    elif type_ == "sponsor":
#        fee = tx_utils.get_fee(NODE_BASE_URL, tx_utils.DEFAULT_SPONSOR_FEE, address, None)
#        params, err_response = get_json_params(content, ["asset_fee"])
#        if err_response:
#            return err_response
#        asset_fee, = params
#        amount = asset_fee
#        tx = tx_utils.sponsor_payload(address, pubkey, None, ASSET_ID, asset_fee, fee, timestamp)
#    elif type_ == "setscript":
#        fee = tx_utils.get_fee(NODE_BASE_URL, tx_utils.DEFAULT_SCRIPT_FEE, address, None)
#        params, err_response = get_json_params(content, ["script"])
#        if err_response:
#            return err_response
#        script, = params
#        tx = tx_utils.set_script_payload(address, pubkey, None, script, fee, timestamp)
#    else:
#        return bad_request("invalid type")
#
#    txid = tx_utils.tx_to_txid(tx)
#    dbtx = WavesTx.from_txid(db.session, txid)
#    if dbtx:
#        return bad_request("txid already exists")
#    dbtx = WavesTx(txid, type, tx_utils.CTX_CREATED, amount, False, json.dumps(tx))
#    db.session.add(dbtx)
#    db.session.commit()
#    return jsonify(dict(txid=txid, state=tx_utils.CTX_CREATED, tx=tx))
#
#@app.route("/tx_status", methods=["POST"])
#def tx_status():
#    content = request.get_json(force=True)
#    if content is None:
#        return bad_request("failed to decode JSON object")
#    params, err_response = get_json_params(content, ["txid"])
#    if err_response:
#        return err_response
#    txid, = params
#    dbtx = WavesTx.from_txid(db.session, txid)
#    if not dbtx:
#        return bad_request('tx not found', 404)
#    tx = dbtx.tx_with_sigs()
#    return jsonify(dict(txid=txid, state=dbtx.state, tx=tx))
#
#@app.route("/tx_serialize", methods=["POST"])
#def tx_serialize():
#    content = request.get_json(force=True)
#    if content is None:
#        return bad_request("failed to decode JSON object")
#    params, err_response = get_json_params(content, ["tx"])
#    if err_response:
#        return err_response
#    tx, = params
#    if not "type" in tx:
#        return bad_request("tx does not contain 'type' field")
#    tx_serialized = tx_utils.tx_serialize(tx)
#    res = {"bytes": base64.b64encode(tx_serialized).decode("utf-8", "ignore")}
#    return jsonify(res)
#
#@app.route("/tx_signature", methods=["POST"])
#def tx_signature():
#    content = request.get_json(force=True)
#    if content is None:
#        return bad_request("failed to decode JSON object")
#    params, err_response = get_json_params(content, ["txid", "signer_index", "signature"])
#    if err_response:
#        return err_response
#    txid, signer_index, signature = params
#    dbtx = WavesTx.from_txid(db.session, txid)
#    if not dbtx:
#        return bad_request('tx not found', 404)
#    logger.info(":: adding sig to tx - %s, %d, %s", txid, signer_index, signature)
#    sig = WavesTxSig(dbtx, signer_index, signature)
#    db.session.add(sig)
#    db.session.commit()
#    tx = dbtx.tx_with_sigs()
#    return jsonify(dict(txid=txid, state=dbtx.state, tx=tx))
#
#@app.route("/tx_broadcast", methods=["POST"])
#def tx_broadcast():
#    content = request.get_json(force=True)
#    if content is None:
#        return bad_request("failed to decode JSON object")
#    params, err_response = get_json_params(content, ["txid"])
#    if err_response:
#        return err_response
#    txid, = params
#    dbtx = WavesTx.from_txid(db.session, txid)
#    if not dbtx:
#        return bad_request('tx not found', 404)
#    tx = dbtx.tx_with_sigs()
#    error = ""
#    # broadcast transaction
#    try:
#        dbtx = tx_utils.broadcast_transaction(db.session, dbtx.txid)
#        db.session.add(dbtx)
#        db.session.commit()
#    except OtherError as ex:
#        error = ex.message
#        if hasattr(ex, 'data'):
#            error = "{} - {}".format(ex.message, ex.data)
#    return jsonify(dict(txid=txid, state=dbtx.state, tx=tx, error=error))
