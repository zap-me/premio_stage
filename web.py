#!/usr/bin/python3

# pylint: disable=import-outside-toplevel
# pylint: disable=unbalanced-tuple-unpacking

import sys
import logging
import json
import datetime
from urllib.parse import urlparse
import math

import gevent
from flask import render_template, request, flash, jsonify
from flask_security import roles_accepted, current_user
#from flask_jsonrpc import JSONRPC
from flask_jsonrpc.exceptions import OtherError
import requests
import pywaves

from app_core import app, db, socketio, SERVER_MODE_WAVES, SERVER_MODE_PAYDB
from models import Role, User, WavesTx, Proposal, Payment, Topic, PushNotificationLocation
import utils
from fcm import FCM
from web_utils import bad_request, get_json_params, get_json_params_optional
import paydb_core
from reward_endpoint import reward, reward_create
# pylint: disable=unused-import
import admin

#jsonrpc = JSONRPC(app, "/api")
logger = logging.getLogger(__name__)
fcm = FCM(app.config["FIREBASE_CREDENTIALS"])

SERVER_MODE = app.config["SERVER_MODE"]
DEEP_LINK_SCHEME = app.config["DEEP_LINK_SCHEME"]
if SERVER_MODE == SERVER_MODE_WAVES:
    import tx_utils
    # our pywaves address object
    PW_ADDRESS = None
    # wave specific config settings
    NODE_BASE_URL = app.config["NODE_BASE_URL"]
    SEED = app.config["WALLET_SEED"]
    ADDRESS = app.config["WALLET_ADDRESS"]
    ASSET_ID = app.config["ASSET_ID"]
    TESTNET = app.config["TESTNET"]
    # master wallet blueprint
    from mw_endpoint import mw
    app.register_blueprint(mw, url_prefix='/mw')
elif SERVER_MODE == SERVER_MODE_PAYDB:
    OPERATIONS_ACCOUNT = app.config["OPERATIONS_ACCOUNT"]
    # paydb blueprint
    from paydb_endpoint import paydb
    app.register_blueprint(paydb, url_prefix='/paydb')
if app.config["USE_STASH"]:
    # stash blueprint
    from stash_endpoint import stash_bp
    app.register_blueprint(stash_bp, url_prefix='/stash')
# reward blueprint
app.register_blueprint(reward, url_prefix='/reward')

def logger_setup(level, handler):
    logger.setLevel(level)
    logger.addHandler(handler)
    if SERVER_MODE == SERVER_MODE_WAVES:
        import mw_endpoint
        mw_endpoint.logger.setLevel(level)
        mw_endpoint.logger.addHandler(handler)
    if SERVER_MODE == SERVER_MODE_PAYDB:
        import paydb_endpoint
        paydb_endpoint.logger.setLevel(level)
        paydb_endpoint.logger.addHandler(handler)

def logger_clear():
    logger.handlers.clear()
    if SERVER_MODE == SERVER_MODE_WAVES:
        import mw_endpoint
        mw_endpoint.logger.handlers.clear()
    if SERVER_MODE == SERVER_MODE_PAYDB:
        import paydb_endpoint
        paydb_endpoint.logger.handlers.clear()

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

def from_int_to_user_friendly(val, divisor, decimal_places=4):
    if not isinstance(val, int):
        return val
    val = val / divisor
    return round(val, decimal_places)

def _create_transaction_waves(recipient, amount, attachment):
    # get fee
    path = f"/assets/details/{ASSET_ID}"
    response = requests.get(NODE_BASE_URL + path)
    if response.ok:
        asset_fee = response.json()["minSponsoredAssetFee"]
    else:
        short_msg = "failed to get asset info"
        logger.error("%s: (%d, %s, %s):\n\t%s", short_msg, response.status_code, response.request.method, response.url, response.text)
        err = OtherError(short_msg, tx_utils.ERR_FAILED_TO_GET_ASSET_INFO)
        err.data = response.text
        raise err
    if not recipient:
        short_msg = "recipient is null or an empty string"
        logger.error(short_msg)
        err = OtherError(short_msg, tx_utils.ERR_EMPTY_ADDRESS)
        raise err
    if not utils.is_address(recipient):
        short_msg = "recipient is not a valid address"
        logger.error(short_msg)
        err = OtherError(short_msg, tx_utils.ERR_EMPTY_ADDRESS)
        raise err
    recipient = pywaves.Address(recipient)
    asset = pywaves.Asset(ASSET_ID)
    address_data = PW_ADDRESS.sendAsset(recipient, asset, amount, attachment, feeAsset=asset, txFee=asset_fee)
    signed_tx = json.loads(address_data["api-data"])
    signed_tx["type"] = 4 # sendAsset does not include "type" - https://github.com/PyWaves/PyWaves/issues/131
    # calc txid properly
    txid = tx_utils.tx_to_txid(signed_tx)
    # store tx in db
    dbtx = WavesTx(txid, "transfer", tx_utils.CTX_CREATED, signed_tx["amount"], True, json.dumps(signed_tx))
    return dbtx

def process_proposals():
    with app.app_context():
        # set expired
        expired = 0
        now = datetime.datetime.now()
        proposals = Proposal.in_status(db.session, Proposal.STATE_AUTHORIZED)
        for proposal in proposals:
            if proposal.date_expiry < now:
                proposal.status = Proposal.STATE_EXPIRED
                expired += 1
                db.session.add(proposal)
        db.session.commit()
        # process authorized
        emails = 0
        sms_messages = 0
        proposals = Proposal.in_status(db.session, Proposal.STATE_AUTHORIZED)
        for proposal in proposals:
            for payment in proposal.payments:
                if payment.status == payment.STATE_CREATED:
                    if payment.email:
                        if SERVER_MODE == SERVER_MODE_PAYDB and User.from_email(db.session, payment.email):
                            _process_claim_paydb(payment, payment.email)
                            utils.email_payment_sent(logger, app.config["ASSET_NAME"], payment)
                            logger.info("Sent payment to %s", payment.email)
                        else:
                            utils.email_payment_claim(logger, app.config["ASSET_NAME"], payment, proposal.HOURS_EXPIRY)
                            payment.status = payment.STATE_SENT_CLAIM_LINK
                            db.session.add(payment)
                            logger.info("Sent payment claim url to %s", payment.email)
                        emails += 1
                    elif payment.mobile:
                        utils.sms_payment_claim(logger, app.config["ASSET_NAME"], payment, proposal.HOURS_EXPIRY)
                        payment.status = payment.STATE_SENT_CLAIM_LINK
                        db.session.add(payment)
                        logger.info("Sent payment claim url to %s", payment.mobile)
                        sms_messages += 1
                    elif payment.recipient:
                        ##TODO: set status and commit before sending so we cannot send twice
                        raise Exception("not yet implemented")
        db.session.commit()
        #logger.info(f"payment statuses commited")
        return f"done (expired {expired}, emails {emails}, SMS messages {sms_messages})"

#
# Jinja2 filters
#

@app.template_filter()
def int2asset(num):
    return utils.int2asset(num)

#
# Flask views
#

@app.route("/")
def index():
    return render_template("index.html")

def process_claim_waves(payment, dbtx, recipient, asset_id):
    if payment.proposal.status != payment.proposal.STATE_AUTHORIZED:
        return dbtx, "payment not authorized"
    if payment.status != payment.STATE_SENT_CLAIM_LINK:
        return dbtx, "payment not authorized"
    # create/get transaction
    if not dbtx:
        if asset_id and asset_id != ASSET_ID:
            return dbtx, "'asset_id' does not match server"
        try:
            dbtx = _create_transaction_waves(recipient, payment.amount, "")
            payment.txid = dbtx.txid
            db.session.add(dbtx)
            db.session.add(payment)
            db.session.commit()
        except OtherError as ex:
            return dbtx, ex.message
        except ValueError as ex:
            return dbtx, ex
    # broadcast transaction
    try:
        dbtx = tx_utils.broadcast_transaction(db.session, dbtx.txid)
        payment.status = payment.STATE_SENT_FUNDS
        db.session.add(dbtx)
        db.session.commit()
    except OtherError as ex:
        return dbtx, ex.message
    return dbtx, None

def _process_claim_paydb(payment, recipient):
    # create transaction, assumes payment hase been validated
    tx, _ = paydb_core.tx_transfer_authorized(db.session, OPERATIONS_ACCOUNT, recipient, payment.amount, "")
    if tx:
        payment.txid = tx.token
        payment.status = payment.STATE_SENT_FUNDS
        db.session.add(payment)
        return tx
    return None


def process_claim_paydb(payment, recipient):
    if payment.proposal.status != payment.proposal.STATE_AUTHORIZED:
        return "payment not authorized"
    if payment.status != payment.STATE_SENT_CLAIM_LINK:
        return "payment not authorized"
    if _process_claim_paydb(payment, recipient):
        db.session.commit()
        return None
    return 'claim failed'

@app.route("/claim_payment/<token>", methods=["GET", "POST"])
def claim_payment(token):
    payment = Payment.from_token(db.session, token)
    if not payment:
        return bad_request('payment not found', 404)
    now = datetime.datetime.now()
    if now > payment.proposal.date_expiry and payment.status != payment.STATE_SENT_FUNDS:
        return bad_request('expired', 404)

    def render(recipient):
        url_parts = urlparse(request.url)
        url = url_parts._replace(scheme=DEEP_LINK_SCHEME, query='scheme={}'.format(url_parts.scheme)).geturl()
        qrcode_svg = utils.qrcode_svg_create(url)
        return render_template("claim_payment.html", payment=payment, recipient=recipient, qrcode_svg=qrcode_svg, url=url)
    def render_waves(dbtx):
        recipient = None
        if dbtx:
            recipient = dbtx.tx_with_sigs()["recipient"]
        return render(recipient)

    if SERVER_MODE == SERVER_MODE_WAVES:
        dbtx = WavesTx.from_txid(db.session, payment.txid)

    if request.method == "POST":
        content_type = request.content_type
        using_app = content_type.startswith('application/json')
        logger.info("claim_payment: content type - %s, using_app - %s", content_type, using_app)
        recipient = ""
        asset_id = ""
        if using_app:
            content = request.get_json(force=True)
            if content is None:
                return bad_request("failed to decode JSON object")
            if SERVER_MODE == SERVER_MODE_WAVES:
                params, err_response = get_json_params(content, ["recipient", "asset_id"])
                if err_response:
                    return err_response
                recipient, asset_id = params
            else: # paydb
                params, err_response = get_json_params(content, ["recipient"])
                if err_response:
                    return err_response
                recipient, = params
        else: # using html form
            try:
                recipient = request.form["recipient"]
            except: # pylint: disable=bare-except
                flash("'recipient' parameter not present", "danger")
                return render_waves(dbtx)
            try:
                asset_id = request.form["asset_id"]
            except: # pylint: disable=bare-except
                pass
        if SERVER_MODE == SERVER_MODE_WAVES:
            dbtx, err_msg = process_claim_waves(payment, dbtx, recipient, asset_id)
        else: # paydb
            err_msg = process_claim_paydb(payment, recipient)
        if err_msg:
            logger.error("claim_payment: %s", err_msg)
            if using_app:
                return bad_request(err_msg)
            flash(err_msg, "danger")
    if SERVER_MODE == SERVER_MODE_WAVES:
        return render_waves(dbtx)
    return render(None)

@app.route("/payment_create", methods=["POST"])
def payment_create():
    return reward_create()

@app.route("/dashboard")
@roles_accepted(Role.ROLE_ADMIN)
def dashboard():
    if SERVER_MODE == SERVER_MODE_WAVES:
        data = dashboard_data_waves()
        data["asset_balance"] = from_int_to_user_friendly(data["asset_balance"], 100)
        data["waves_balance"] = from_int_to_user_friendly(data["waves_balance"], 10**8)
        data["master_asset_balance"] = from_int_to_user_friendly(data["master_asset_balance"], 100)
        data["master_waves_balance"] = from_int_to_user_friendly(data["master_waves_balance"], 10**8)
        return render_template("dashboard_waves.html", data=data)
    data = dashboard_data_paydb()
    data["premio_stage_balance"] = from_int_to_user_friendly(data["premio_stage_balance"], 100)
    data["total_balance"] = from_int_to_user_friendly(data["total_balance"], 100)
    return render_template("dashboard_paydb.html", data=data)

# https://gis.stackexchange.com/a/2964
def meters_to_lat_lon_displacement(meters, origin_latitude):
    lat = meters / 111111
    lon = meters / (111111 * math.cos(math.radians(origin_latitude)))
    return lat, lon

@app.route("/push_notifications", methods=["GET", "POST"])
@roles_accepted(Role.ROLE_ADMIN)
def push_notifications():
    type_ = ''
    topic = ''
    title = ''
    body = ''
    image = ''
    html = ''
    location = ''
    registration_token = ''
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        image = request.form["image"]
        html = request.form["html"]
        try:
            type_ = request.form["type"]
            if type_ == "topic":
                topic = request.form["topic"]
                fcm.send_to_topic(topic, title, body, image, html)
                flash(f"sent push notification ({topic})", "success")
            elif type_ == "location":
                location = request.form["location"]
                parts = location.split(',')
                if len(parts) != 4:
                    raise Exception('invalid location parameter')
                latitude, longitude, max_dist_meters, max_age_minutes = parts
                latitude = float(latitude)
                longitude = float(longitude)
                max_dist_meters = int(max_dist_meters)
                max_age_minutes = int(max_age_minutes)
                max_lat_delta, max_long_delta = meters_to_lat_lon_displacement(max_dist_meters, latitude)
                tokens = PushNotificationLocation.tokens_at_location(db.session, latitude, max_lat_delta, longitude, max_long_delta, max_age_minutes)
                tokens = [x.fcm_registration_token for x in tokens]
                fcm.send_to_tokens(tokens, title, body, image, html)
                count = len(tokens)
                flash(f"sent push notification ({count} devices)", "success")
            else:
                registration_token = request.form["registration_token"]
                fcm.send_to_tokens([registration_token], title, body, image, html)
                flash("sent push notification", "success")
        except Exception as e: # pylint: disable=broad-except
            flash("{}".format(str(e.args[0])), "danger")
    topics = Topic.topic_list(db.session)
    return render_template("push_notifications.html", topics=topics, type_=type_, topic=topic, location=location, title=title, body=body, image=image, html=html, registration_token=registration_token)

@app.route("/push_notifications_register", methods=["POST"])
def push_notifications_register():
    content = request.get_json(force=True)
    if content is None:
        return bad_request("failed to decode JSON object")
    params, err_response = get_json_params(content, ["registration_token"])
    if err_response:
        return err_response
    registration_token, = params
    latitude, longitude = get_json_params_optional(content, ["latitude", "longitude"])
    topics = Topic.topic_list(db.session)
    fcm.subscribe_to_topics(registration_token, topics)
    if latitude and longitude:
        latitude = float(latitude)
        longitude = float(longitude)
        push_location = PushNotificationLocation.from_token(db.session, registration_token)
        if push_location:
            push_location.update(latitude, longitude)
        else:
            push_location = PushNotificationLocation(registration_token, latitude, longitude)
        db.session.add(push_location)
        db.session.commit()
    return jsonify(dict(result="ok"))

@app.route("/issue", methods=["GET", "POST"])
@roles_accepted(Role.ROLE_ADMIN)
def issue():
    amount = ''
    if request.method == "POST":
        amount = request.form["amount"]
        amount_int = int(float(amount) * 100)
        tx, error = paydb_core.tx_issue_authorized(db.session, current_user.email, amount_int, None)
        if tx:
            flash(f"issued {amount}", "success")
        else:
            flash(error, "danger")
    return render_template("issue.html", amount=amount)

##
## JSON-RPC
##
#
#@jsonrpc.method("status")
#def status():
#    return dashboard_data()
#
#@jsonrpc.method("getaddress")
#def getaddress():
#    return {"address": ADDRESS}
#
#@jsonrpc.method("getbalance")
#def getbalance():
#    path = f"/assets/balance/{ADDRESS}/{ASSET_ID}"
#    response = requests.get(NODE_BASE_URL + path)
#    return response.json()
#
#@jsonrpc.method("gettransaction")
#def gettransaction(txid):
#    path = f"/transactions/info/{txid}"
#    response = requests.get(NODE_BASE_URL + path)
#    return response.json()
#
#@jsonrpc.method("createtransaction")
#def createtransaction(recipient, amount, attachment):
#    dbtx = _create_transaction(recipient, amount, attachment)
#    db.session.add(dbtx)
#    db.session.commit()
#    # return txid/state to caller
#    return {"txid": dbtx.txid, "state": dbtx.state}
#
#@jsonrpc.method("broadcasttransaction")
#def broadcasttransaction(txid):
#    dbtx = _broadcast_transaction(txid)
#    db.session.add(dbtx)
#    db.session.commit()
#    # return txid/state to caller
#    return {"txid": txid, "state": dbtx.state}
#
#@jsonrpc.method("expiretransactions")
#def expiretransactions(above_age=60*60*24):
#    count = WavesTx.expire_transactions(db.session, above_age, CTX_CREATED, CTX_EXPIRED)
#    db.session.commit()
#    return {"count": count}
#
#@jsonrpc.method("validateaddress")
#def validateaddress(address):
#    if pywaves.validateAddress(address):
#        return {"address": address}
#    err = OtherError("invalid address", 0)
#    raise err


#
# gevent class
#

class WebGreenlet():

    def __init__(self, exception_func, addr="0.0.0.0", port=5000):
        self.addr = addr
        self.port = port
        self.runloop_greenlet = None
        self.process_proposals_greenlet = None
        self.exception_func = exception_func

    def check_wallet(self):
        # check address object matches our configured address
        global PW_ADDRESS # pylint: disable=global-statement
        PW_ADDRESS = pywaves.Address(seed=SEED)
        addr = PW_ADDRESS.address
        if isinstance(addr, bytes):
            addr = addr.decode()
        if addr != ADDRESS:
            msg = f"PW_ADDRESS ({addr}) does not match {ADDRESS}"
            logger.error(msg)
            sys.exit(1)

    def start(self):
        def runloop():
            logger.info("WebGreenlet runloop started")
            logger.info("WebGreenlet webserver starting (addr: %s, port: %d)", self.addr, self.port)
            socketio.run(app, host=self.addr, port=self.port)

        def process_proposals_loop():
            while True:
                gevent.spawn(process_proposals)
                gevent.sleep(30)

        def start_greenlets():
            if SERVER_MODE == SERVER_MODE_WAVES:
                logger.info("checking wallet...")
                self.check_wallet()
            logger.info("starting WebGreenlet runloop...")
            self.runloop_greenlet.start()
            self.process_proposals_greenlet.start()

        # create greenlet
        self.runloop_greenlet = gevent.Greenlet(runloop)
        self.process_proposals_greenlet = gevent.Greenlet(process_proposals_loop)
        if self.exception_func:
            self.runloop_greenlet.link_exception(self.exception_func)
        # check node/wallet and start greenlets
        gevent.spawn(start_greenlets)

    def stop(self):
        self.runloop_greenlet.kill()
        self.process_proposals_greenlet.kill()
        gevent.joinall([self.runloop_greenlet, self.process_proposals_greenlet])

def run():
    # setup logging
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('[%(name)s %(levelname)s] %(message)s'))
    logger.addHandler(handler)
    # clear loggers set by any imported modules
    logging.getLogger().handlers.clear()

    web_greenlet = WebGreenlet(None)
    web_greenlet.start()

    while 1:
        gevent.sleep(1)

    web_greenlet.stop()

if __name__ == "__main__":
    run()
