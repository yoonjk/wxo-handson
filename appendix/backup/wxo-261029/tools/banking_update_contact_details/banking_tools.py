from datetime import datetime
import json
from decimal import Decimal, InvalidOperation
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

import banking_db as db


# Utility function (reuse your date validator)
def _is_valid_date(date_str: str) -> bool:
    """Check if the provided date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


@tool(name="banking_fetch_account_id", description="Fetch the account ID(s) linked to a customer username or customer number. A customer may have more than one account.", permission=ToolPermission.ADMIN)
def banking_fetch_account_id(identifier: str) -> str:
    """Return the account ID(s) linked to a customer identifier (username or customer number).

    A single identifier can be linked to more than one account (e.g. a
    checking and a savings account), so this returns a JSON list rather
    than a single value.

    Args:
        identifier (str): Customer's username or customer number.

    Returns:
        str: A JSON string like {"accounts": ["ACC10001", "ACC10004"]}.
            The list is empty if no account is linked to the identifier.
    """
    account_ids = db.fetch_account_ids(identifier)
    return json.dumps({"accounts": account_ids})


@tool(
    name="banking_list_customer_accounts",
    description="List all accounts (including their balances) linked to a customer username or customer number.",
    permission=ToolPermission.ADMIN
)
def banking_list_customer_accounts(identifier: str) -> str:
    """Return every account linked to a customer identifier, with balances.

    Use this when the user provides a username/customer number and wants
    to see their accounts (e.g. an account picker screen). Each entry
    includes the account ID, currency, available balance, and ledger balance.

    Args:
        identifier (str): Customer's username or customer number.

    Returns:
        str: A JSON string like:
            {"accounts": [{"account_id": "ACC10001", "currency": "USD",
                            "available": "12500.75", "ledger": "12750.75"}, ...]}
            The list is empty if no account is linked to the identifier.
    """
    accounts = db.fetch_accounts_with_balance(identifier)
    return json.dumps({"accounts": accounts})


@tool(name="banking_retrieve_account_balance", description="Get account balance for a given account ID.", permission=ToolPermission.ADMIN)
def banking_retrieve_account_balance(account_id: str) -> str:
    """Retrieve the current balance for an account.

    Args:
        account_id (str): Account identifier.

    Returns:
        str: A JSON string with the balance details, or a JSON error message.
    """
    balance = db.fetch_account_balance(account_id)
    if balance is None:
        return json.dumps({"error": "account not found"})
    return json.dumps(balance)


@tool(
    name="banking_get_account_detail",
    description="Get detailed information for a specific account (balances plus registered contact info). Use this after the user selects an account from their account list.",
    permission=ToolPermission.ADMIN
)
def banking_get_account_detail(account_id: str) -> str:
    """Return the account detail view for a single account.

    Includes balances and the registered contact info (email/phone).
    Intended to be called after the user picks a specific account from a
    list (e.g. from banking_list_customer_accounts).

    Args:
        account_id (str): Account identifier.

    Returns:
        str: A JSON string with account_id, currency, available, ledger,
            email, and phone, or a JSON error message if not found.
    """
    detail = db.fetch_account_detail(account_id)
    if detail is None:
        return json.dumps({"error": "account not found"})
    return json.dumps(detail)


@tool(
    name="banking_list_recent_transactions",
    description="List recent transactions for an account within optional date range.",
    permission=ToolPermission.ADMIN
)
def banking_list_recent_transactions(
    account_id: str,
    start_date: str = None,
    end_date: str = None,
    limit: str = "20"  # Default as string for safety with orchestrator inputs
) -> str:
    """Return a list of recent transactions for the account.

    Handles missing or invalid 'limit' parameter gracefully.

    Args:
        account_id (str): Account identifier.
        start_date (str, optional): Start date filter in YYYY-MM-DD format.
        end_date (str, optional): End date filter in YYYY-MM-DD format.
        limit (str, optional): Maximum number of transactions to return. Defaults to "20".

    Returns:
        str: A JSON string with the list of transactions, or a JSON error message.
    """

    # --- Validate and normalize limit ---
    if limit is None or str(limit).strip() == "":
        parsed_limit = 20
    else:
        try:
            parsed_limit = int(limit)
            if parsed_limit < 0:
                parsed_limit = 20
        except (ValueError, TypeError):
            parsed_limit = 20

    # --- Validate dates if provided ---
    if start_date and not _is_valid_date(start_date):
        return json.dumps({"error": f"Invalid start_date: {start_date}. Expected YYYY-MM-DD."})
    if end_date and not _is_valid_date(end_date):
        return json.dumps({"error": f"Invalid end_date: {end_date}. Expected YYYY-MM-DD."})

    txns = db.fetch_transactions(account_id, start_date, end_date, parsed_limit)
    if txns is None:
        return json.dumps({"error": "account not found"})

    return json.dumps(txns)


@tool(
    name="banking_get_recent_transactions",
    description="Get the most recent transactions for an account. Specify a count to control how many are returned (default 2).",
    permission=ToolPermission.ADMIN
)
def banking_get_recent_transactions(account_id: str, count: str = "2") -> str:
    """Return the most recent transactions for an account, most recent first.

    Args:
        account_id (str): Account identifier.
        count (str, optional): Number of most recent transactions to return. Defaults to "2".

    Returns:
        str: A JSON string with the list of transactions, or a JSON error message.
    """
    # --- Validate and normalize count ---
    if count is None or str(count).strip() == "":
        parsed_count = 2
    else:
        try:
            parsed_count = int(count)
            if parsed_count <= 0:
                parsed_count = 2
        except (ValueError, TypeError):
            parsed_count = 2

    txns = db.fetch_transactions(account_id, limit=parsed_count)
    if txns is None:
        return json.dumps({"error": "account not found"})

    return json.dumps(txns)


@tool(name="banking_get_branch_code", description="Get branch code given branch name or city.", permission=ToolPermission.ADMIN)
def banking_get_branch_code(branch_query: str) -> str:
    """Return the branch code for a branch name or city search.

    Args:
        branch_query (str): Branch name or city (case-insensitive).

    Returns:
        str: The branch code, or "-1" if not found.
    """
    branch_code = db.fetch_branch_code(branch_query)
    return branch_code if branch_code else "-1"


@tool(name="banking_update_contact_details", description="Update the contact details (email/phone) for given account ID.", permission=ToolPermission.ADMIN)
def banking_update_contact_details(account_id: str, email: str = None, phone: str = None) -> str:
    """Update contact details for an account.

    Args:
        account_id (str): Account identifier.
        email (str, optional): New email address.
        phone (str, optional): New phone number.

    Returns:
        str: A success or error message.
    """
    if not account_id:
        return "Account ID must be provided."
    if not email and not phone:
        return "Either email or phone must be provided to update."

    updated = db.update_contact_details(account_id, email, phone)
    if not updated:
        return f"Account {account_id} not found."

    updates = {}
    if email:
        updates["email"] = email
    if phone:
        updates["phone"] = phone
    return f"Contact details for {account_id} updated: {json.dumps(updates)}"


@tool(name="banking_initiate_funds_transfer", description="Initiate a funds transfer between two accounts (internal).", permission=ToolPermission.ADMIN)
def banking_initiate_funds_transfer(from_account: str, to_account: str, amount: str, currency: str = "USD", reference: str = None) -> str:
    """Initiate a funds transfer between two accounts.

    Validates the amount and accounts, then performs an atomic balance
    update in MySQL.

    Args:
        from_account (str): Source account ID.
        to_account (str): Destination account ID.
        amount (str): Amount as a string (e.g., "100.50").
        currency (str, optional): Currency code. Defaults to "USD".
        reference (str, optional): Optional transaction reference/note.

    Returns:
        str: A JSON string with the transfer status, or a JSON error message.
    """
    # Basic checks
    if from_account == to_account:
        return json.dumps({"error": "from_account and to_account must be different"})

    # Validate amount
    try:
        amt = Decimal(amount)
    except (InvalidOperation, TypeError):
        return json.dumps({"error": f"Invalid amount: {amount}"})
    if amt <= 0:
        return json.dumps({"error": "Amount must be greater than zero"})

    tx_id = f"FT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    status = "initiated"

    try:
        db.transfer_funds(tx_id, from_account, to_account, amt, currency, reference)
    except db.AccountNotFoundError as e:
        missing = str(e)
        field = "from_account" if missing == from_account else "to_account"
        return json.dumps({"error": f"{field} not found"})
    except db.InsufficientFundsError:
        return json.dumps({"error": "Insufficient funds"})

    result = {
        "transaction_id": tx_id,
        "from": from_account,
        "to": to_account,
        "amount": str(amt),
        "currency": currency,
        "status": status,
        "reference": reference or ""
    }
    return json.dumps(result)


@tool(
    name="banking_get_transfer_history",
    description="Get the transfer history (incoming and outgoing) for a specific account. Use this when the user wants to see past transfers for an account, as opposed to raw transactions.",
    permission=ToolPermission.ADMIN
)
def banking_get_transfer_history(account_id: str, limit: str = "20") -> str:
    """Return the transfer history for an account, most recent first.

    Each entry is tagged with a "direction" of "outgoing" (this account was
    the source) or "incoming" (this account was the destination).

    Args:
        account_id (str): Account identifier.
        limit (str, optional): Maximum number of transfer records to return. Defaults to "20".

    Returns:
        str: A JSON string with the list of transfer records, or a JSON error message.
    """
    # --- Validate and normalize limit ---
    if limit is None or str(limit).strip() == "":
        parsed_limit = 20
    else:
        try:
            parsed_limit = int(limit)
            if parsed_limit <= 0:
                parsed_limit = 20
        except (ValueError, TypeError):
            parsed_limit = 20

    history = db.fetch_transfer_history(account_id, parsed_limit)
    if history is None:
        return json.dumps({"error": "account not found"})

    return json.dumps(history)