import logging
import threading
from types import SimpleNamespace

from models import Role, User, Permission, PayDbTransaction

logger = logging.getLogger(__name__)
user_balances = SimpleNamespace(lock=threading.Lock(), kvstore=None)

def __balance(user):
    ## assumes lock is held
    if not user.token in user_balances.kvstore:
        return 0
    return user_balances.kvstore[user.token]

def __balance_total():
    ## assumes lock is held
    balance = 0
    for val in user_balances.kvstore.values():
        balance += val
    return balance

def __tx_play(txn):
    ## assumes lock is held
    if not txn.sender.token in user_balances.kvstore:
        user_balances.kvstore[txn.sender.token] = 0
    if txn.recipient and not txn.recipient.token in user_balances.kvstore:
        user_balances.kvstore[txn.recipient.token] = 0
    if txn.action == txn.ACTION_ISSUE:
        user_balances.kvstore[txn.sender.token] += txn.amount
    if txn.action == txn.ACTION_TRANSFER:
        user_balances.kvstore[txn.sender.token] -= txn.amount
        user_balances.kvstore[txn.recipient.token] += txn.amount
    if txn.action == txn.ACTION_DESTROY:
        user_balances.kvstore[txn.sender.token] -= txn.amount

def __tx_play_all(session):
    ## assumes lock is held
    assert not user_balances.kvstore
    user_balances.kvstore = {}
    for tx in PayDbTransaction.all(session):
        __tx_play(tx)

def __check_balances_inited(session):
    ## assumes lock is held
    # check user_balances.kvstore has been initialized
    if user_balances.kvstore is None:
        logger.info('user_balances.kvstore not initialized, initializing now..')
        __tx_play_all(session)

def user_balance_from_user(session, user):
    with user_balances.lock:
        __check_balances_inited(session)
        return __balance(user)

def user_balance(session, api_key):
    if not api_key.has_permission(Permission.PERMISSION_BALANCE):
        return -1
    return user_balance_from_user(session, api_key.user)

def balance_total(session):
    with user_balances.lock:
        __check_balances_inited(session)
        return __balance_total()

def tx_play_all(session):
    with user_balances.lock:
        __tx_play_all(session)

def tx_transfer_authorized(session, sender_email, recipient_email, amount, attachment):
    logger.info('%s: %s: %s, %s', sender_email, recipient_email, amount, attachment)
    with user_balances.lock:
        __check_balances_inited(session)
        error = ''
        sender = User.from_email(session, sender_email)
        recipient = User.from_email(session, recipient_email)
        if not sender:
            error = f'ACTION_TRANSFER: sender ({sender_email}) is not valid'
        elif not recipient:
            error = f'ACTION_TRANSFER: recipient ({recipient_email}) is not valid'
        if error:
            logger.error(error)
            return None, error
        sender_balance = __balance(sender)
        if sender_balance < amount:
            error = f'ACTION_TRANSFER: user balance ({sender_balance}) is too low'
            logger.error(error)
            return None, error
        tx = PayDbTransaction(PayDbTransaction.ACTION_TRANSFER, sender, recipient, amount, attachment)
        __tx_play(tx)
        session.add(tx)
        session.commit()
        return tx, ''

def tx_issue_authorized(session, sender_email, amount, attachment):
    logger.info('%s: %s, %s', sender_email, amount, attachment)
    with user_balances.lock:
        __check_balances_inited(session)
        error = ''
        sender = User.from_email(session, sender_email)
        if not sender:
            error = f'ACTION_ISSUE: sender ({sender_email}) is not valid'
        if error:
            logger.error(error)
            return None, error
        tx = PayDbTransaction(PayDbTransaction.ACTION_ISSUE, sender, sender, amount, attachment)
        __tx_play(tx)
        session.add(tx)
        session.commit()
        return tx, ''

def tx_create_and_play(session, api_key, action, recipient_email, amount, attachment):
    logger.info('%s (%s): %s: %s, %s, %s', api_key.token, api_key.user.email, action, recipient_email, amount, attachment)
    with user_balances.lock:
        __check_balances_inited(session)
        error = ''
        user = api_key.user
        if not user.is_active:
            error = f'{action}: {user.email} is not active'
        elif amount <= 0:
            error = f'{action}: amount ({amount}) is less then or equal to zero'
        if error:
            logger.error(error)
            return None, error
        recipient = User.from_email(session, recipient_email)
        if action not in PayDbTransaction.ACTIONS:
            error = f'{action}: is not a valid action'
        else:
            if action == PayDbTransaction.ACTION_ISSUE:
                if not api_key.has_permission(Permission.PERMISSION_ISSUE):
                    error = f'ACTION_ISSUE: {api_key.token} is not authorized'
                elif not user.has_role(Role.ROLE_ADMIN):
                    error = f'ACTION_ISSUE: {user.email} is not authorized'
                elif not recipient == user:
                    error = f'ACTION_ISSUE: recipient should be {user.email}'
            if action == PayDbTransaction.ACTION_TRANSFER:
                user_bal = __balance(user)
                if not api_key.has_permission(Permission.PERMISSION_TRANSFER):
                    error = f'ACTION_TRANSFER: {api_key.token} is not authorized'
                elif not recipient:
                    error = f'ACTION_TRANSFER: recipient ({recipient_email}) is not valid'
                elif user_bal < amount:
                    error = f'ACTION_TRANSFER: user balance ({user_bal}) is too low'
            if action == PayDbTransaction.ACTION_DESTROY:
                user_bal = __balance(user)
                if not api_key.has_permission(Permission.PERMISSION_TRANSFER):
                    error = f'ACTION_TRANSFER: {api_key.token} is not authorized'
                elif not recipient == user:
                    error = f'ACTION_ISSUE: recipient should be {user.email}'
                elif user_bal < amount:
                    error = f'ACTION_DESTROY: user balance ({user_bal}) is too low'
        if error:
            logger.error(error)
            return None, error
        tx = PayDbTransaction(action, user, recipient, amount, attachment)
        __tx_play(tx)
        session.add(tx)
        session.commit()
        return tx, ''
