# IBM Bob Notifier Extension

VS Code extension for IBM Bob IDE 2.0.1. It subscribes to the IBM Bob Notification MCP Server's authenticated SSE feed and opens one custom popup screen when a Service Request or targeted notification arrives.

The notification list is a Bob webview popup styled with the supplied logo. Its header contains the unread count and **Mark all as read**. The table has `Message`, `Link`, and `Received` columns, shows at most five rows per page, and uses Carbon-style paging for larger lists. Notification messages can contain up to ten titled resource links; the row's link button opens a single link directly or lets the user choose one when several links are attached. Double-clicking a row copies the message and marks that row read. The `Copy Message` button copies the selected message. `Confirm` marks the visible page read; closing the popup or pressing Escape preserves unread state. The popup has no Cancel button. The newest notification is displayed first and up to 100 items are retained across Bob restarts.

Only a server-authorized administrator sees the header `+` button. It switches the same popup to the **IBM Bob Notification > Send** screen. Admins can send to all registered users, one group, or multiple selected individuals. The Users & Groups forms show visible Carbon-blue checkmarks for group membership and notification-admin toggles. The screen includes recipient search and counts, optional Request ID and link, a 200-character message field, a popup preview, and a `Send to N` action. Returning to the list uses `Back to notifications`. Incoming events do not replace the composer while it is being edited. Copy and send feedback appears as an in-popup toast. The extension runs inside Bob and calls the VS Code Extension API; a remote MCP server cannot call `vscode.window` directly.

## Requirements

- IBM Bob IDE 2.0.1 (Bob's changelog lists the VS Code engine uplift to 1.116.0).
- Node.js 18 or later and npm for packaging.
- IBM Bob Notification MCP Server running with its `/events` SSE feed reachable from the Bob client.
- Bob users and groups initialized in the FastAPI database. The legacy JSON environment values are imported only when the user database is empty.

## Build a VSIX

Run these commands in this directory:

```bash
npm install
npm run package
```

The package is written as `bob-notifier-1.8.1.vsix`.

## Install in IBM Bob

1. Open Bob's **Extensions** view.
2. Open the view's `...` menu and choose **Install from VSIX...**.
3. Select `bob-notifier-1.8.1.vsix` and reload Bob if prompted.
4. In Bob, open the Command Palette and run **IBM Bob Notifier: Set Bearer Token**. Enter the raw token mapped to this Bob user's employee number, without the `Bearer ` prefix. The token is stored in VS Code SecretStorage, not in `settings.json`.
5. Set `ibmBobNotification.sseUrl` to the endpoint reachable from Bob. Existing `itsmSrNotifier.*` values are read as a fallback after upgrading. For example:

   ```json
   {
     "ibmBobNotification.sseUrl": "https://itsm.example.com:8032/events",
     "ibmBobNotification.autoStart": false
   }
   ```

6. Run **IBM Bob Notifier: Start** from the Command Palette. The status bar shows the connection state.

For a local server on the same computer, the default is `http://127.0.0.1:8032/events`. If the notification MCP server runs on another host or container, replace `127.0.0.1` with its reachable DNS name/IP. Use HTTPS when traffic crosses a network.

## Commands

| Command | Purpose |
|---|---|
| `IBM Bob Notifier: Start` | Connect to the SSE feed and reconnect after network loss |
| `IBM Bob Notifier: Stop` | Close the connection |
| `IBM Bob Notifier: Open Notifications` | Open the single notification popup screen |
| `IBM Bob Notifier: Test Popup` | Open the popup screen with sample rows |
| `IBM Bob Notifier: Clear Notifications` | Remove retained notification items |
| `IBM Bob Notifier: Set Bearer Token` | Store/update the token in SecretStorage |
| `IBM Bob Notifier: Replay Events` | Reset the saved cursor so retained outbox events are replayed |

On every SSE message, the extension logs `[event_received]`; for each new notification it logs `[notification_added]` after adding the entry to the popup table. The extension persists the last SSE event ID in Bob's global extension state and sends it as `Last-Event-ID` and `after_event_id` on reconnect. The server derives the employee number from the per-user token and sends only matching SR assignments or notification scopes. Admins can open the `Users & Groups` button on the Send screen to register users, issue one-time tokens, create groups, and add active users to groups. Group creation and member addition use separate side panels; member selection supports search and multiple users. The extension adds `service_request.created` and `notification.created` events to the single popup table; other SR status/worklog events advance the cursor without opening a popup. General notification rows show `title · message` and retain their resource links.

## ITSM demo server setup

Start the FastAPI app and IBM Bob Notification MCP Server from the project root. Set these values in `.env` (legacy `SR_EVENT_*` variable names remain accepted):

```dotenv
ITSM_API_BASE_URL=http://127.0.0.1:8000
ITSM_API_TOKEN=<same token configured for FastAPI>
ITSM_EVENT_MCP_BEARER_TOKEN=<long random token>
ITSM_EVENT_MCP_HOST=0.0.0.0
ITSM_EVENT_MCP_PORT=8032
# Imported only once when the Bob user tables are empty.
ITSM_EVENT_USER_TOKENS_JSON={"EMP1001":"<unique employee 1001 token>","EMP1002":"<unique employee 1002 token>"}
ITSM_EVENT_USER_GROUPS_JSON={"EMP1001":["operations"],"EMP1002":["operations","managers"]}
ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON=["EMP1001"]
```

`ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON` seeds the initial admin role only when the Bob user tables are empty. The manager screen later controls admin access through the database. The plus button appears after the user token is accepted by the server; the admin API checks the role on every request. Configure an optional `ibmBobNotification.adminBaseUrl` only when the admin API is not at `<SSE origin>/admin`.

The first FastAPI startup imports these JSON values into the Bob user tables only if there are no registered users. Afterward, manage users, tokens, roles, groups, and memberships in **Users & Groups**; environment values are not synchronized on restarts. The database stores only token hashes and their final four characters. Group names created in the manager start with a lowercase letter. The admin screen supports all registered users, one group, or multiple selected users; per-user delivery and read receipts are recorded in the new notification tables. For a ready-made development dataset, apply `sql/005_create_bob_notification_management.sql` and then `sql/006_seed_bob_notification_sample_data.sql`; the sample token values are listed in `docs/bob_notification_sample_data.md`.

```bash
python -m itsm_event_mcp.server
```

Create an SR through the authenticated FastAPI API with `assignee_employee_no` set. The API writes the SR and recipient employee number into the outbox in the same MySQL transaction. The Event MCP Server validates the Bob user's token, derives the employee number from its server-side map, and emits only SRs assigned to that employee on `/events`.

For a repeatable end-to-end test, keep the Bob listener running and, in another terminal at the ITSM project root, run:

```bash
python -m scripts.test_bob_popup --assignee-employee-no EMP1001
```

The script creates a uniquely named SR for `EMP1001`, verifies its recipient-specific `service_request.created` outbox event, and prints its SR key. Replace EMP1001 with an employee number in the token map and connect the matching Bob user. Confirm the designed SR popup screen opens in Bob and later SRs appear as table rows, newest first. The **IBM Bob Notifier** Output channel logs `[event_received]`, `[badge_update]`, and `[notification_added]`.

## Troubleshooting

- **401**: Set the extension token to the exact per-user value mapped under the employee number in `ITSM_EVENT_USER_TOKENS_JSON` and restart the listener.
- **Connection refused / timeout**: Check the host, port 8032, firewall, and whether the address is reachable from the Bob client. `127.0.0.1` always means the Bob machine itself.
- **No popup**: Confirm `[event_received]` appears in the `IBM Bob Notifier` Output channel and that `event_type` is `service_request.created`. Run `IBM Bob Notifier: Test Popup` to open the popup design preview independently of SSE. Inspect `[popup_test_show_called]` and `[popup_test_error]`; for real events inspect `[popup_opened]` and `[notification_added]`.
- **Replay**: Run `IBM Bob Notifier: Replay Events`, then stop and start the listener.
- **No chat transcript entry**: This extension uses the VS Code Webview API; it does not insert text into Bob's chat history.

## Compatibility note

The manifest targets VS Code engine `^1.116.0`, which IBM Bob 2.0.1's official changelog lists as its embedded engine. Install the VSIX through Bob's Extensions view. Validate custom-extension installation against your organization's extension policy before distributing it broadly.
