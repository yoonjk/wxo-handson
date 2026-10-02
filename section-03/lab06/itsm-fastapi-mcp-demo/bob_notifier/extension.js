"use strict";

const vscode = require("vscode");

const CONFIG_SECTION = "ibmBobNotification";
const LEGACY_CONFIG_SECTION = "itsmSrNotifier";
const SECRET_KEY = "itsmSrNotifier.bearerToken";
const CURSOR_KEY = "itsmSrNotifier.lastEventId";
const NOTIFICATIONS_KEY = "itsmSrNotifier.notifications";
const READ_NOTIFICATIONS_KEY = "itsmSrNotifier.readNotificationIds";
const MAX_NOTIFICATIONS = 100;
const PAGE_SIZE = 5;

let output;
let statusBar;
let notificationStatusBar;
let activeController;
let connectionTask;
let notificationPanel;
let usersGroupsPanel;
let notificationItems = [];
let popupPreview = false;
let extensionContext;
let currentPage = 0;
let selectedEventId;
let readNotificationIds = new Set();
let adminConfig = { isAdmin: false, groups: [], groupCounts: {}, employees: [], employeeGroups: {} };
let adminDrawerOpen = false;
let adminFormDraft = {};

function getAdminBaseUrl() {
  const configured = getConfig().get("adminBaseUrl", "").trim();
  if (configured) return configured.replace(/\/$/, "");
  const sseUrl = getConfig().get("sseUrl", "http://127.0.0.1:8032/events");
  try { return new URL(sseUrl).origin + "/admin"; } catch { return ""; }
}

async function refreshAdminConfig(context) {
  const token = await context.secrets.get(SECRET_KEY);
  const baseUrl = getAdminBaseUrl();
  if (!token || !baseUrl) {
    adminConfig = { isAdmin: false, groups: [], groupCounts: {}, employees: [], employeeGroups: {} };
    updatePopup();
    return;
  }
  try {
    const response = await fetch(`${baseUrl}/targets`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const targets = await response.json();
    adminConfig = {
      isAdmin: true,
      groups: Array.isArray(targets.groups) ? targets.groups : [],
      groupCounts: targets.group_counts && typeof targets.group_counts === "object" ? targets.group_counts : {},
      employees: Array.isArray(targets.employees) ? targets.employees : [],
      employeeGroups: targets.employee_groups && typeof targets.employee_groups === "object" ? targets.employee_groups : {},
    };
    output.appendLine(`[admin_access] enabled groups=${adminConfig.groups.length} employees=${adminConfig.employees.length}`);
  } catch (error) {
    adminConfig = { isAdmin: false, groups: [], groupCounts: {}, employees: [], employeeGroups: {} };
    output.appendLine(`[admin_access] disabled reason=${error.message}`);
  }
  updatePopup();
}

function renderAdminOptions(values) {
  return values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

async function callAdminApi(context, path, method = "GET", body) {
  const token = await context.secrets.get(SECRET_KEY);
  const response = await fetch(`${getAdminBaseUrl()}/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token || ""}`,
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

async function syncReadReceipts(context, items) {
  const notificationIds = [...new Set(items.map((item) => item.notification_id).filter(Boolean))];
  if (!notificationIds.length) return;
  const token = await context.secrets.get(SECRET_KEY);
  const sseUrl = new URL(getConfig().get("sseUrl", "http://127.0.0.1:8032/events"));
  try {
    const response = await fetch(`${sseUrl.origin}/receipts/read`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token || ""}`, "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ notification_ids: notificationIds }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch (error) {
    output.appendLine(`[receipt_sync_error] ${error.message}`);
  }
}

function showUsersGroupsPanel(context) {
  if (!adminConfig.isAdmin) return;
  if (!usersGroupsPanel) {
    usersGroupsPanel = vscode.window.createWebviewPanel(
      "ibmBobUsersGroups", "IBM Bob Notification > Users & Groups", vscode.ViewColumn.Active,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    usersGroupsPanel.onDidDispose(() => { usersGroupsPanel = undefined; }, null, context.subscriptions);
    usersGroupsPanel.webview.onDidReceiveMessage(async (message) => {
      if (message.command === "manage-show-notifications") {
        usersGroupsPanel?.dispose();
        if (notificationPanel) notificationPanel.reveal(vscode.ViewColumn.Active, false);
        else showNotificationPopup(context);
        return;
      }
      // Native confirm() dialogs are unreliable in VS Code/Bob webviews.
      // Confirm destructive actions in the extension host instead.
      if (message.command === "manage-rotate-token") {
        const answer = await vscode.window.showWarningMessage(
          `Issue a new token for ${message.employeeNo}? The current token will stop working immediately.`,
          { modal: true }, "Issue token",
        );
        if (answer !== "Issue token") return;
      } else if (message.command === "manage-deactivate-user") {
        const answer = await vscode.window.showWarningMessage(
          `Deactivate ${message.employeeNo} and revoke their token?`,
          { modal: true }, "Deactivate",
        );
        if (answer !== "Deactivate") return;
      } else if (message.command === "manage-delete-group") {
        const answer = await vscode.window.showWarningMessage(
          `Delete group ${message.groupName}?`,
          { modal: true }, "Delete group",
        );
        if (answer !== "Delete group") return;
      }
      if (message.command === "manage-copy-token") {
        if (typeof message.token === "string" && message.token) {
          await vscode.env.clipboard.writeText(message.token);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: "Token copied. Save it now; it cannot be shown again." });
        }
        return;
      }
      try {
        let data;
        if (message.command === "manage-load") {
          const [users, groups, targets] = await Promise.all([
            callAdminApi(context, "users"), callAdminApi(context, "groups"), callAdminApi(context, "targets"),
          ]);
          data = { type: "manage-data", users: users.users || [], groups: groups.groups || [], targets };
        } else if (message.command === "manage-create-user") {
          const created = await callAdminApi(context, "users", "POST", message.user);
          usersGroupsPanel?.webview.postMessage({ type: "manage-token-issued", token: created.token, employeeNo: created.employee_no });
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `User ${created.employee_no} registered.` });
        } else if (message.command === "manage-update-user") {
          await callAdminApi(context, `users/${encodeURIComponent(message.employeeNo)}`, "PUT", message.user);
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `User ${message.employeeNo} updated.` });
        } else if (message.command === "manage-deactivate-user") {
          await callAdminApi(context, `users/${encodeURIComponent(message.employeeNo)}`, "DELETE");
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `User ${message.employeeNo} deactivated.` });
        } else if (message.command === "manage-rotate-token") {
          const rotated = await callAdminApi(context, `users/${encodeURIComponent(message.employeeNo)}/token`, "POST", {});
          usersGroupsPanel?.webview.postMessage({ type: "manage-token-issued", token: rotated.token, employeeNo: rotated.employee_no });
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `New token issued for ${message.employeeNo}.` });
        } else if (message.command === "manage-create-group") {
          const created = await callAdminApi(context, "groups", "POST", { group_name: message.groupName, description: message.description || null });
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage(data);
          usersGroupsPanel?.webview.postMessage({ type: "manage-group-created", groupName: created.group_name });
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `Group ${created.group_name} created. Add members when ready.` });
        } else if (message.command === "manage-delete-group") {
          await callAdminApi(context, `groups/${encodeURIComponent(message.groupName)}`, "DELETE");
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `Group ${message.groupName} deleted.` });
        } else if (message.command === "manage-add-members") {
          for (const employeeNo of message.employeeNos || []) {
            await callAdminApi(context, `groups/${encodeURIComponent(message.groupName)}/members/${encodeURIComponent(employeeNo)}`, "PUT", {});
          }
          data = await loadUsersGroups(context);
          usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `${message.employeeNos.length} member${message.employeeNos.length === 1 ? "" : "s"} added to ${message.groupName}.` });
        } else if (message.command === "manage-remove-member") {
          await callAdminApi(context, `groups/${encodeURIComponent(message.groupName)}/members/${encodeURIComponent(message.employeeNo)}`, "DELETE");
          data = await loadUsersGroups(context);
        }
        if (data) usersGroupsPanel?.webview.postMessage(data);
      } catch (error) {
        usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `Could not complete the action: ${error.message}` });
      }
    }, null, context.subscriptions);
  } else {
    usersGroupsPanel.reveal(vscode.ViewColumn.Active, false);
  }
  renderUsersGroupsHtml(usersGroupsPanel.webview);
  void loadUsersGroups(context).then((data) => usersGroupsPanel?.webview.postMessage(data)).catch((error) => {
    usersGroupsPanel?.webview.postMessage({ type: "manage-toast", message: `Could not load users and groups: ${error.message}` });
  });
}

async function loadUsersGroups(context) {
  const [users, groups, targets] = await Promise.all([
    callAdminApi(context, "users"), callAdminApi(context, "groups"), callAdminApi(context, "targets"),
  ]);
  return { type: "manage-data", users: users.users || [], groups: groups.groups || [], targets };
}

function renderUsersGroupsHtml(webview) {
  const nonce = require("crypto").randomBytes(16).toString("base64");
  webview.html = `<!DOCTYPE html>
  <html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource}; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <style>
    *{box-sizing:border-box}body{margin:0;padding:20px 28px 16px;font-family:'IBM Plex Sans','IBM Plex Sans KR',system-ui,sans-serif;color:var(--vscode-foreground);background:var(--vscode-editor-background)}
    button,input,select{font:inherit;color:inherit}button{cursor:pointer}.top{display:flex;align-items:center;gap:18px;border-bottom:1px solid var(--vscode-panel-border);padding-bottom:14px}.crumb{border:0;background:none;color:var(--vscode-textLink-foreground);padding:0}.top-right{margin-left:auto;display:flex;gap:18px;align-items:center}.head{display:flex;align-items:center;gap:12px;margin:20px 0 8px}.head h1{font-size:26px;font-weight:400;margin:0}.sub{color:var(--vscode-descriptionForeground);margin:0 0 22px}.tabs{display:flex;gap:20px;border-bottom:1px solid var(--vscode-panel-border);margin-bottom:16px}.tab{background:none;border:0;padding:10px 6px;border-bottom:3px solid transparent}.tab[aria-selected="true"]{border-bottom-color:var(--vscode-focusBorder);font-weight:600}.toolbar{display:flex;gap:10px;align-items:center;margin:14px 0}.toolbar input,.toolbar select,.field input,.field select,.search{height:38px;padding:0 10px;background:var(--vscode-input-background);border:1px solid var(--vscode-input-border);color:var(--vscode-input-foreground)}.toolbar input{min-width:240px}.primary{margin-left:auto;border:0;background:#0f62fe;color:#fff;padding:10px 16px}.secondary{border:1px solid var(--vscode-button-border,transparent);background:var(--vscode-button-secondaryBackground);color:var(--vscode-button-secondaryForeground);padding:7px 10px}.link{border:0;background:transparent;color:var(--vscode-textLink-foreground);padding:5px}.danger{color:var(--vscode-errorForeground)}table{width:100%;border-collapse:collapse}th{background:var(--vscode-editorWidget-background);text-align:left;font-weight:600}th,td{padding:12px 10px;border-bottom:1px solid var(--vscode-panel-border);vertical-align:middle}.tag{display:inline-block;margin:2px 4px 2px 0;padding:3px 8px;border-radius:12px;background:var(--vscode-badge-background);color:var(--vscode-badge-foreground);font-size:12px}.status{white-space:nowrap}.dot{color:#24a148}.empty{padding:22px;color:var(--vscode-descriptionForeground)}.groups-layout{display:grid;grid-template-columns:minmax(220px,30%) 1fr;min-height:380px;border:1px solid var(--vscode-panel-border)}.group-list{border-right:1px solid var(--vscode-panel-border);padding:12px}.group-list .search{width:100%;margin-bottom:10px}.drawer .search{width:100%}.group-item{width:100%;padding:11px;border:0;text-align:left;background:transparent;display:flex;justify-content:space-between}.group-item.active{border-left:3px solid var(--vscode-focusBorder);background:var(--vscode-list-activeSelectionBackground);color:var(--vscode-list-activeSelectionForeground)}.group-detail{padding:18px}.group-title{display:flex;align-items:flex-start;gap:12px}.group-title h2{margin:0 0 4px;font-size:20px;font-weight:400}.group-title p{margin:0;color:var(--vscode-descriptionForeground)}.member-add{display:flex;gap:8px;max-width:620px;margin:20px 0 12px}.member-add input{flex:1}.config{margin-top:18px;padding:12px 16px;border-left:3px solid var(--vscode-focusBorder);background:var(--vscode-editorWidget-background);font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-word}.config[hidden],.view[hidden],.modal[hidden],.token-box[hidden]{display:none}.config-title{display:flex;justify-content:space-between;align-items:center;font-family:inherit}.modal{position:fixed;inset:0;background:#0008;display:flex;justify-content:flex-end;z-index:5}.drawer{width:min(520px,100%);height:100%;overflow:auto;background:var(--vscode-editor-background);padding:20px;box-shadow:-4px 0 20px #0004}.drawer.wide{width:min(600px,100%)}.panel-note{padding:12px;background:var(--vscode-editorWidget-background);color:var(--vscode-descriptionForeground);font-size:13px}.selection-count{margin:10px 0;color:var(--vscode-descriptionForeground)}.primary:disabled{opacity:.55;cursor:default}.drawer-head{display:flex;align-items:center;justify-content:space-between}.drawer-head h2{font-size:22px;font-weight:400}.field{margin:16px 0}.field label{display:block;margin-bottom:6px;color:var(--vscode-descriptionForeground)}.field input{width:100%}.field label.admin-toggle{display:flex;align-items:center;gap:10px;margin:0;color:var(--vscode-foreground);cursor:pointer}.field input[type=checkbox]{appearance:none;-webkit-appearance:none;display:grid;place-content:center;width:18px;height:18px;min-width:18px;flex:0 0 18px;margin:0;padding:0;border:1px solid var(--vscode-checkbox-border,var(--vscode-input-border));border-radius:2px;background:var(--vscode-checkbox-background,var(--vscode-input-background));cursor:pointer}.field input[type=checkbox]:checked{border-color:#0f62fe;background:#0f62fe}.field input[type=checkbox]::after{content:"";width:5px;height:9px;border:solid var(--vscode-checkbox-foreground,#fff);border-width:0 2px 2px 0;transform:rotate(45deg) scale(0);margin-top:-2px}.field input[type=checkbox]:checked::after{transform:rotate(45deg) scale(1)}.field input[type=checkbox]:focus-visible{outline:2px solid var(--vscode-focusBorder);outline-offset:2px}.check-list{max-height:190px;overflow:auto;border:1px solid var(--vscode-panel-border);padding:6px}.check-list label{display:flex;gap:8px;padding:7px;color:var(--vscode-foreground)}.check-list input{width:auto;height:auto}.token-box{margin-top:18px;padding:14px;background:#fcf4d6;color:#393939;border-left:4px solid #f1c21b}.token-value{display:flex;gap:8px;margin-top:10px}.token-value code{flex:1;overflow-wrap:anywhere;padding:8px;background:white}.footer{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;padding:16px 0;background:var(--vscode-editor-background)}.toast{position:fixed;right:24px;top:20px;z-index:8;padding:12px 16px;background:var(--vscode-notifications-background);box-shadow:0 2px 8px #0005}.toast[hidden]{display:none}@media(max-width:760px){body{padding:14px}.groups-layout{grid-template-columns:1fr}.group-list{border-right:0;border-bottom:1px solid var(--vscode-panel-border)}.toolbar{flex-wrap:wrap}.toolbar input{min-width:140px}}
  </style></head><body>
    <div class="top"><img src="${webview.asWebviewUri(vscode.Uri.joinPath(extensionContext.extensionUri,"media","bob-logo.png"))}" width="28" height="28" alt="IBM Bob"><button class="crumb" id="show-notifications">Notifications</button><span>/</span><button class="crumb" id="show-send">Send</button><span>/</span><strong>Users &amp; Groups</strong><span class="tag">Admin</span><div class="top-right"><button class="link" id="show-notifications-top">♧ Show notifications</button><button class="link" id="close-panel" aria-label="Close">✕</button></div></div>
    <div class="head"><h1>Users &amp; Groups</h1></div><p class="sub">Register Bob users, manage one-time tokens, and map users to notification groups.</p>
    <div class="tabs"><button class="tab" id="users-tab" aria-selected="true">Users <span id="user-count">0</span></button><button class="tab" id="groups-tab" aria-selected="false">Group mapping <span id="group-count">0</span></button></div>
    <section class="view" id="users-view"><div class="toolbar"><input id="user-search" placeholder="Search by employee no."><label>Group</label><select id="user-group-filter"><option value="">All groups</option></select><button class="primary" id="register-user">Register user ＋</button></div><div id="users-table"></div></section>
    <section class="view" id="groups-view" hidden><div class="groups-layout"><aside class="group-list"><input class="search" id="group-search" placeholder="Search groups"><button class="primary" id="open-create-group" style="width:100%;margin:0 0 12px">New group ＋</button><div id="group-list-items"></div><div id="group-total" class="empty"></div></aside><div class="group-detail" id="group-detail"><p class="empty">Select a group to manage members.</p></div></div></section>
    
    <div class="modal" id="group-modal" hidden><div class="drawer"><div class="drawer-head"><h2>Create group</h2><button class="link" id="close-group-form">✕</button></div><p class="panel-note">Create a group to organize Bob users and target notifications. Group names start with a lowercase letter and can contain lowercase letters, numbers, periods, hyphens, and underscores.</p><form id="group-form"><div class="field"><label for="group-name">Group name</label><input id="group-name" required maxlength="64" pattern="[a-z][a-z0-9._-]*" placeholder="e.g. operations"><div id="group-validation" class="sub">Use a lowercase starting letter and only a-z, 0-9, ., - or _.</div></div><div class="field"><label for="group-description">Description (optional)</label><input id="group-description" maxlength="255" placeholder="Describe this group"></div><div class="footer"><button type="button" class="secondary" id="cancel-group-form">Cancel</button><button type="submit" class="primary" id="save-group">Create group</button></div></form></div></div><div class="modal" id="members-modal" hidden><div class="drawer wide"><div class="drawer-head"><h2 id="members-title">Add members</h2><button class="link" id="close-members-form">✕</button></div><p class="sub" id="members-subtitle"></p><div class="field"><label for="member-search">Search employee no.</label><input class="search" id="member-search" placeholder="Search employee no."></div><div class="check-list" id="member-candidates"></div><div class="selection-count" id="member-selection-count">0 selected</div><div class="footer"><button class="secondary" id="cancel-members-form">Cancel</button><button class="primary" id="save-members" disabled>Add 0 members</button></div></div></div><div class="modal" id="user-modal" hidden><div class="drawer"><div class="drawer-head"><h2 id="form-title">Register user</h2><button class="link" id="close-user-form">✕</button></div><form id="user-form"><div class="field"><label for="employee-no">Employee no.</label><input id="employee-no" required maxlength="32" pattern="[A-Za-z0-9._-]+"><div id="employee-validation" class="sub"></div></div><div class="field"><label>Groups</label><input class="search" id="form-group-search" placeholder="Search groups"><div class="check-list" id="form-groups"></div></div><div class="field"><label class="admin-toggle" for="is-admin"><input type="checkbox" id="is-admin"><span>Notification admin</span></label><div class="sub">Can send notifications and manage users and groups.</div></div><div class="token-box" id="token-box" hidden><strong>Token generated. Copy it now; it is shown only once.</strong><p>In the employee's Bob client, run <b>IBM Bob Notifier: Set Bearer Token</b> and paste this value without the <code>Bearer </code> prefix.</p><div class="token-value"><code id="issued-token"></code><button type="button" class="secondary" id="copy-token">Copy</button></div></div><div class="footer"><button type="button" class="secondary" id="cancel-user-form">Cancel</button><button type="submit" class="primary" id="save-user">Register</button></div></form></div></div>
    <div class="toast" id="toast" hidden></div>
    <script nonce="${nonce}">
      const vscode=acquireVsCodeApi();let users=[],groups=[],targets={},selectedGroup='',editingEmployee='',issuedToken='';
      const el=id=>document.getElementById(id);const esc=value=>String(value==null?'':value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      function toast(message){el('toast').textContent=message;el('toast').hidden=false;setTimeout(()=>el('toast').hidden=true,4000)}
      function send(command,data){vscode.postMessage(Object.assign({command},data||{}))}
      
      function renderUsers(){const term=el('user-search').value.toLowerCase(),filter=el('user-group-filter').value;const rows=users.filter(u=>(!term||u.employee_no.toLowerCase().includes(term))&&(!filter||u.group_names.includes(filter)));el('user-count').textContent=String(users.length);el('users-table').innerHTML=rows.length?'<table><thead><tr><th>Employee no.</th><th>Groups</th><th>Role</th><th>Token</th><th></th></tr></thead><tbody>'+rows.map(u=>'<tr><td>'+esc(u.employee_no)+(u.status==='inactive'?' <span class="tag">Inactive</span>':'')+'</td><td>'+u.group_names.map(g=>'<span class="tag">'+esc(g)+'</span>').join('')+'</td><td>'+(u.is_admin?'<span class="tag">Admin</span>':'User')+'</td><td class="status">'+(u.status==='active'&&u.token_masked?'<span class="dot">●</span> Issued '+esc(u.token_masked):esc(u.token_status))+'</td><td><button class="link" data-edit="'+esc(u.employee_no)+'">Edit</button> '+(u.status==='active'?'<button class="link" data-rotate="'+esc(u.employee_no)+'">Issue token</button><button class="link danger" data-deactivate="'+esc(u.employee_no)+'">Deactivate</button>':'')+'</td></tr>').join('')+'</tbody></table>':'<div class="empty">No matching users.</div>';el('users-table').querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>openUserForm(b.dataset.edit));el('users-table').querySelectorAll('[data-rotate]').forEach(b=>b.onclick=()=>send('manage-rotate-token',{employeeNo:b.dataset.rotate}));el('users-table').querySelectorAll('[data-deactivate]').forEach(b=>b.onclick=()=>send('manage-deactivate-user',{employeeNo:b.dataset.deactivate}))}
      function renderGroupOptions(){const select=el('user-group-filter'),current=select.value;select.innerHTML='<option value="">All groups</option>'+groups.map(g=>'<option value="'+esc(g.group_name)+'">'+esc(g.group_name)+'</option>').join('');select.value=current;el('group-count').textContent=String(groups.length);el('group-total').textContent=groups.length+' groups';el('form-groups').innerHTML=groups.map(g=>'<label><input type="checkbox" value="'+esc(g.group_name)+'"><span>'+esc(g.group_name)+'</span></label>').join('')||'<div class="empty">Create a group first.</div>';renderGroupList()}
      function renderGroupList(){const term=el('group-search').value.toLowerCase();const list=groups.filter(g=>g.group_name.toLowerCase().includes(term));el('group-list-items').innerHTML=list.map(g=>'<button class="group-item '+(g.group_name===selectedGroup?'active':'')+'" data-group="'+esc(g.group_name)+'"><span>'+esc(g.group_name)+'</span><span>'+g.member_count+'</span></button>').join('');el('group-list-items').querySelectorAll('[data-group]').forEach(b=>b.onclick=()=>{selectedGroup=b.dataset.group;renderGroupList();renderGroupDetail()})}
      function renderGroupDetail(){const g=groups.find(x=>x.group_name===selectedGroup);if(!g){el('group-detail').innerHTML='<p class="empty">Select a group to manage members.</p>';return}el('group-detail').innerHTML='<div class="group-title"><div><h2>'+esc(g.group_name)+'</h2><p>'+esc(g.description||'')+(g.description?' · ':'')+g.members.length+' members · used for group notifications</p></div><div style="margin-left:auto;display:flex;gap:8px"><button class="secondary" id="open-add-members">Add members ＋</button><button class="link danger" id="delete-group">Delete group</button></div></div><table><thead><tr><th>Employee no.</th><th>Other groups</th><th>Role</th><th></th></tr></thead><tbody>'+g.members.map(no=>{const u=users.find(x=>x.employee_no===no);return '<tr><td>'+esc(no)+'</td><td>'+((u&&u.group_names||[]).filter(x=>x!==g.group_name).map(x=>'<span class="tag">'+esc(x)+'</span>').join('')||'—')+'</td><td>'+(u&&u.is_admin?'<span class="tag">Admin</span>':'User')+'</td><td><button class="link" data-remove="'+esc(no)+'">Remove</button></td></tr>'}).join('')+'</tbody></table>';el('open-add-members').onclick=()=>openMembersForm(g);el('delete-group').onclick=()=>send('manage-delete-group',{groupName:g.group_name});el('group-detail').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>send('manage-remove-member',{groupName:g.group_name,employeeNo:b.dataset.remove}))}
      function render(){renderGroupOptions();renderUsers();if(selectedGroup&&!groups.some(g=>g.group_name===selectedGroup))selectedGroup='';renderGroupList();renderGroupDetail()}
      function openUserForm(employee){editingEmployee=employee||'';issuedToken='';el('token-box').hidden=true;el('save-user').hidden=false;el('form-title').textContent=editingEmployee?'Edit user':'Register user';el('save-user').textContent=editingEmployee?'Save changes':'Register';el('employee-no').disabled=Boolean(editingEmployee);el('employee-no').value='';el('is-admin').checked=false;el('form-groups').querySelectorAll('input').forEach(x=>x.checked=false);if(editingEmployee){const user=users.find(u=>u.employee_no===editingEmployee);el('employee-no').value=user.employee_no;el('is-admin').checked=user.is_admin;el('form-groups').querySelectorAll('input').forEach(x=>x.checked=user.group_names.includes(x.value))}el('user-modal').hidden=false}
      function closeUserForm(){el('user-modal').hidden=true;editingEmployee='';issuedToken=''}
      let membersGroupName='';
      function openGroupForm(){el('group-name').value='';el('group-description').value='';el('group-modal').hidden=false;validateGroupName();el('group-name').focus()}
      function closeGroupForm(){el('group-modal').hidden=true}
      function validateGroupName(){const name=el('group-name').value.trim(),valid=/^[a-z][a-z0-9._-]{0,63}$/.test(name),duplicate=groups.some(g=>g.group_name.toLowerCase()===name.toLowerCase());el('group-name').setCustomValidity(!name?'Enter a group name.':!valid?'Use a lowercase starting letter and only a-z, 0-9, ., - or _.':duplicate?'This group name already exists.':'');el('group-validation').textContent=duplicate?'This group name already exists.':'Use a lowercase starting letter and only a-z, 0-9, ., - or _.';el('group-validation').className='sub'+(duplicate?' danger':'');el('save-group').disabled=!valid||duplicate;return valid&&!duplicate}
      function openMembersForm(group){membersGroupName=group.group_name;el('members-title').textContent='Add members to '+group.group_name;el('members-subtitle').textContent='Select active registered users who are not already in this group.';el('member-search').value='';renderMemberCandidates();el('members-modal').hidden=false}
      function closeMembersForm(){el('members-modal').hidden=true;membersGroupName=''}
      function renderMemberCandidates(){const group=groups.find(g=>g.group_name===membersGroupName);if(!group)return;const term=el('member-search').value.trim().toLowerCase(),candidates=users.filter(u=>u.status==='active'&&!group.members.includes(u.employee_no)&&u.employee_no.toLowerCase().includes(term));el('member-candidates').innerHTML=candidates.length?candidates.map(u=>'<label><input type="checkbox" value="'+esc(u.employee_no)+'"><span>'+esc(u.employee_no)+'</span></label>').join(''):'<div class="empty">No eligible users found.</div>';el('member-candidates').querySelectorAll('input').forEach(box=>box.onchange=updateMemberSelection);updateMemberSelection()}
      function updateMemberSelection(){const count=el('member-candidates').querySelectorAll('input:checked').length;el('member-selection-count').textContent=count+' selected';el('save-members').textContent='Add '+count+' member'+(count===1?'':'s');el('save-members').disabled=count===0}
      el('users-tab').onclick=()=>{el('users-tab').setAttribute('aria-selected','true');el('groups-tab').setAttribute('aria-selected','false');el('users-view').hidden=false;el('groups-view').hidden=true};el('groups-tab').onclick=()=>{el('users-tab').setAttribute('aria-selected','false');el('groups-tab').setAttribute('aria-selected','true');el('users-view').hidden=true;el('groups-view').hidden=false};el('register-user').onclick=()=>openUserForm('');el('close-user-form').onclick=closeUserForm;el('cancel-user-form').onclick=closeUserForm;el('user-search').oninput=renderUsers;el('user-group-filter').onchange=renderUsers;el('group-search').oninput=renderGroupList;el('form-group-search').oninput=()=>{const t=el('form-group-search').value.toLowerCase();el('form-groups').querySelectorAll('label').forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(t))};el('open-create-group').onclick=openGroupForm;el('close-group-form').onclick=closeGroupForm;el('cancel-group-form').onclick=closeGroupForm;el('close-members-form').onclick=closeMembersForm;el('cancel-members-form').onclick=closeMembersForm;el('member-search').oninput=renderMemberCandidates;el('group-name').oninput=validateGroupName;el('group-form').onsubmit=event=>{event.preventDefault();if(!validateGroupName())return;send('manage-create-group',{groupName:el('group-name').value.trim(),description:el('group-description').value.trim()||null})};el('save-members').onclick=()=>{const employeeNos=[...el('member-candidates').querySelectorAll('input:checked')].map(x=>x.value);if(employeeNos.length)send('manage-add-members',{groupName:membersGroupName,employeeNos})};el('show-notifications').onclick=()=>send('manage-show-notifications');el('show-notifications-top').onclick=()=>send('manage-show-notifications');el('show-send').onclick=()=>send('manage-show-notifications');el('close-panel').onclick=()=>send('manage-show-notifications');
      el('user-form').onsubmit=event=>{event.preventDefault();const employee=el('employee-no').value.trim();const groupNames=[...el('form-groups').querySelectorAll('input:checked')].map(x=>x.value);const data={group_names:groupNames,is_admin:el('is-admin').checked,status:'active'};if(editingEmployee)send('manage-update-user',{employeeNo:editingEmployee,user:data});else send('manage-create-user',{user:Object.assign({employee_no:employee},data)});closeUserForm()};el('copy-token').onclick=()=>send('manage-copy-token',{token:issuedToken});
      window.addEventListener('message',event=>{const data=event.data||{};if(data.type==='manage-data'){users=data.users||[];groups=data.groups||[];targets=data.targets||{};render()}if(data.type==='manage-group-created'){selectedGroup=data.groupName;el('groups-tab').click();closeGroupForm();renderGroupList();renderGroupDetail()}if(data.type==='manage-token-issued'){issuedToken=data.token;editingEmployee=data.employeeNo;el('form-title').textContent='Token issued';el('save-user').hidden=true;el('employee-no').disabled=true;el('employee-no').value=data.employeeNo;el('token-box').hidden=false;el('issued-token').textContent=data.token;el('user-modal').hidden=false}if(data.type==='manage-toast')toast(data.message)});send('manage-load');
    </script></body></html>`;
}

function getConfig() {
  const current = vscode.workspace.getConfiguration(CONFIG_SECTION);
  const legacy = vscode.workspace.getConfiguration(LEGACY_CONFIG_SECTION);
  return {
    get(key, defaultValue) {
      // Prefer a value explicitly set under the new prefix. Otherwise read the
      // legacy key so an upgrade does not discard the user's existing URL or auto-start choice.
      const configured = current.inspect(key);
      const explicitlyConfigured = configured && [
        configured.globalValue,
        configured.workspaceValue,
        configured.workspaceFolderValue,
      ].some((value) => value !== undefined);
      return explicitlyConfigured ? current.get(key, defaultValue) : legacy.get(key, defaultValue);
    },
  };
}

function setStatus(text, tooltip) {
  if (!statusBar) return;
  statusBar.text = `$(bell) SR ${text}`;
  statusBar.tooltip = tooltip;
  statusBar.show();
}

function getUnreadCount() {
  return notificationItems.filter((item) => !readNotificationIds.has(String(item.event_id))).length;
}

function formatBadgeCount(count) {
  return count > 99 ? "99+" : String(count);
}

function updateNotificationStatus() {
  const unreadCount = getUnreadCount();
  if (notificationStatusBar) {
    notificationStatusBar.text = `$(bell) SR 알림 ${formatBadgeCount(unreadCount)}`;
    notificationStatusBar.tooltip = "클릭하여 SR 알림 popup 목록 열기";
    notificationStatusBar.show();
  }
  // Keep the badge current in an already-open Bob Webview, not just on next render.
  if (notificationPanel) {
    void notificationPanel.webview.postMessage({ type: "unread-count", count: unreadCount });
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function parseTimestamp(value) {
  if (!value) return undefined;
  let raw = String(value).trim();
  const compactUtc = raw.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (compactUtc) raw = `${compactUtc[1]}-${compactUtc[2]}-${compactUtc[3]}T${compactUtc[4]}:${compactUtc[5]}:${compactUtc[6]}Z`;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function formatFullTimestamp(value) {
  const date = parseTimestamp(value);
  if (!date) return String(value ?? "—");
  const part = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${part(date.getMonth() + 1)}-${part(date.getDate())} ${part(date.getHours())}:${part(date.getMinutes())}:${part(date.getSeconds())}`;
}

function relativeTime(value, now = new Date()) {
  const date = parseTimestamp(value);
  if (!date) return "—";
  const minutes = Math.floor(Math.max(0, now.getTime() - date.getTime()) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const sameDay = (left, right) => left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() && left.getDate() === right.getDate();
  if (sameDay(date, now)) { const hours = Math.floor(minutes / 60); return `${hours} hr${hours === 1 ? "" : "s"} ago`; }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getSafeLink(item) {
  const direct = [item.url, item.link, item.details_url, item.detail_url, item.service_request_url]
    .find((value) => typeof value === "string" && /^https?:\/\//i.test(value));
  const fromText = `${item.title || ""}`.match(/https?:\/\/[^\s<>()]+/i)?.[0];
  const candidate = direct || fromText;
  if (!candidate) return undefined;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

function getSafeLinks(item) {
  const links = Array.isArray(item.links) ? item.links : [];
  const safeLinks = links.map((link) => {
    if (!link || typeof link.url !== "string" || !/^https?:\/\//i.test(link.url)) return undefined;
    try {
      const url = new URL(link.url);
      if (!["http:", "https:"].includes(url.protocol)) return undefined;
      return { title: typeof link.title === "string" && link.title.trim() ? link.title.trim() : url.host, url: url.toString() };
    } catch {
      return undefined;
    }
  }).filter(Boolean).slice(0, 10);
  if (safeLinks.length) return safeLinks;
  const legacyLink = getSafeLink(item);
  if (!legacyLink) return [];
  const url = new URL(legacyLink);
  return [{ title: url.host, url: url.toString() }];
}

function copyTextForItem(item) {
  return item.event_type === "notification.created"
    ? `${item.title} · ${item.message}`
    : `${item.ticket_key} · ${item.title}`;
}

function popupRows() {
  const rows = notificationItems.slice().sort((a, b) => {
    try {
      const left = BigInt(String(a.event_id));
      const right = BigInt(String(b.event_id));
      return left === right ? 0 : (left > right ? -1 : 1);
    } catch {
      return String(b.event_id).localeCompare(String(a.event_id));
    }
  });
  if (popupPreview) {
    rows.unshift({
      event_id: "popup-test",
      ticket_key: "SR-POPUP-TEST",
      title: "Bob 팝업 E2E 테스트 메시지",
      links: [
        { title: "SR record", url: "https://jira.example.com/browse/SR-POPUP-TEST" },
        { title: "Runbook", url: "https://example.com/runbooks/sr-popup-test" },
      ],
      created_at: new Date().toISOString(),
    });
  }
  return rows;
}

function getPageNumbers(page, pageCount) {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, index) => index);
  const pages = new Set([0, pageCount - 1, page - 1, page, page + 1]);
  return [...pages].filter((item) => item >= 0 && item < pageCount).sort((a, b) => a - b);
}

function renderPopupHtml(webview) {
  const allRows = popupRows();
  const pageCount = Math.max(1, Math.ceil(allRows.length / PAGE_SIZE));
  currentPage = Math.min(currentPage, pageCount - 1);
  const pageRows = allRows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  if (!pageRows.some((item) => String(item.event_id) === String(selectedEventId))) {
    selectedEventId = pageRows[0]?.event_id;
  }
  const logoUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionContext.extensionUri, "media", "bob-logo.png")
  );
  const tableRows = pageRows.map((item) => {
    const isGeneralNotification = item.event_type === "notification.created";
    const messageHeading = isGeneralNotification ? item.title : item.ticket_key;
    const messageDetail = isGeneralNotification ? item.message : ` · ${item.title}`;
    const messageText = copyTextForItem(item);
    const isSelected = String(item.event_id) === String(selectedEventId);
    const safeLinks = getSafeLinks(item);
    const date = parseTimestamp(item.created_at);
    const datetime = date ? date.toISOString() : "";
    const linkButton = safeLinks.length
      ? `<button class="link-button" type="button" data-links="${escapeHtml(JSON.stringify(safeLinks))}" title="${safeLinks.length} resource link${safeLinks.length === 1 ? "" : "s"}" aria-label="Choose from ${safeLinks.length} resource link${safeLinks.length === 1 ? "" : "s"}">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9.5 2H14v4.5h-1.5V4.56L7.53 9.53 6.47 8.47l4.97-4.97H9.5V2ZM12.5 8v5.5h-10v-10H8V5H4v7h7V8h1.5Z" fill="currentColor"/></svg>
          ${safeLinks.length > 1 ? `<span>${safeLinks.length}</span>` : ""}
        </button>` : "";
    return `
      <tr data-event-id="${escapeHtml(item.event_id)}" class="${isSelected ? "selected" : ""}">
        <td class="message-cell">
          <button class="message-select" type="button" data-event-id="${escapeHtml(item.event_id)}" aria-pressed="${isSelected}" title="${escapeHtml(messageText)}">
            <strong>${escapeHtml(messageHeading)}</strong><span class="message-body"> · ${escapeHtml(messageDetail || "")}</span>
          </button>
        </td>
        <td class="link-cell">${linkButton}</td>
        <td class="time-cell"><time datetime="${escapeHtml(datetime)}" title="${escapeHtml(formatFullTimestamp(item.created_at))}" data-created-at="${escapeHtml(item.created_at)}">${escapeHtml(relativeTime(item.created_at))}</time></td>
      </tr>`;
  }).join("") || '<tr><td class="empty" colspan="3">No messages.</td></tr>';

  const pageNumbers = getPageNumbers(currentPage, pageCount);
  let previousPage;
  const pageButtons = pageNumbers.map((page) => {
    const gap = previousPage !== undefined && page - previousPage > 1
      ? '<li class="ellipsis" aria-hidden="true">…</li>' : "";
    previousPage = page;
    return `${gap}<li><button class="page-number" data-page="${page}" aria-label="Page ${page + 1}" ${page === currentPage ? 'aria-current="page"' : ""}>${page + 1}</button></li>`;
  }).join("");
  const pagination = pageCount > 1 ? `
      <nav class="pagination" aria-label="Pagination">
        <ul>
          <li><button data-page="0" aria-label="First page" ${currentPage === 0 ? "disabled" : ""}><span aria-hidden="true">|‹</span></button></li>
          <li><button data-page="${Math.max(0, currentPage - 1)}" aria-label="Previous page" ${currentPage === 0 ? "disabled" : ""}><span aria-hidden="true">‹</span></button></li>
          ${pageButtons}
          <li><button data-page="${Math.min(pageCount - 1, currentPage + 1)}" aria-label="Next page" ${currentPage === pageCount - 1 ? "disabled" : ""}><span aria-hidden="true">›</span></button></li>
          <li><button data-page="${pageCount - 1}" aria-label="Last page" ${currentPage === pageCount - 1 ? "disabled" : ""}><span aria-hidden="true">›|</span></button></li>
        </ul>
      </nav>` : "";
  const unreadCount = getUnreadCount();
  const badge = unreadCount > 0
    ? `<span id="unread-badge" class="unread-badge" aria-label="Unread ${unreadCount}">${formatBadgeCount(unreadCount)}</span>` : '<span id="unread-badge" class="unread-badge" aria-label="Unread 0" hidden></span>';
  const themeClass = [vscode.ColorThemeKind.Dark, vscode.ColorThemeKind.HighContrast]
    .includes(vscode.window.activeColorTheme.kind) ? "theme-dark" : "theme-light";
  const cardHeight = pageRows.length === PAGE_SIZE ? "456px" : "auto";
  const safeScriptJson = (value) => JSON.stringify(value).replace(/</g, "\\u003c");
  const adminGroupsJson = safeScriptJson(adminConfig.groups);
  const adminGroupCountsJson = safeScriptJson(adminConfig.groupCounts);
  const adminEmployeesJson = safeScriptJson(adminConfig.employees);
  const employeeGroupsJson = safeScriptJson(adminConfig.employeeGroups);
  const initialTargetTypeJson = safeScriptJson(adminFormDraft.targetType || "all");
  const selectedEmployeeNos = new Set(Array.isArray(adminFormDraft.employeeNos) ? adminFormDraft.employeeNos : []);
  const groupRows = adminConfig.groups.map((group) => `<button class="target-row group-row ${group === adminFormDraft.targetGroup ? "checked" : ""}" type="button" data-group="${escapeHtml(group)}" data-search="${escapeHtml(group.toLowerCase())}" role="radio" aria-checked="${group === adminFormDraft.targetGroup}"><span class="radio-mark"></span><span class="target-name">${escapeHtml(group)}</span><span class="target-meta">${Number(adminConfig.groupCounts[group] || 0)} members</span></button>`).join("");
  const employeeRows = adminConfig.employees.map((employee) => {
    const groups = adminConfig.employeeGroups[employee] || [];
    const selected = selectedEmployeeNos.has(employee);
    return `<label class="target-row employee-row" data-employee-row="${escapeHtml(employee.toLowerCase())} ${escapeHtml(groups.join(" ").toLowerCase())}"><input type="checkbox" class="employee-check" value="${escapeHtml(employee)}" ${selected ? "checked" : ""}><span class="target-name">${escapeHtml(employee)}</span><span class="target-meta">${escapeHtml(groups.join(", "))}</span></label>`;
  }).join("");
  const initialTargetType = ["all", "group", "user"].includes(adminFormDraft.targetType) ? adminFormDraft.targetType : "all";
  const requestIdValue = escapeHtml(adminFormDraft.requestId || "");
  const messageValue = escapeHtml(adminFormDraft.message || "");
  const linkUrlValue = escapeHtml(adminFormDraft.linkUrl || "");
  const nonce = require("crypto").randomBytes(16).toString("base64");

  webview.html = `<!DOCTYPE html>
  <html lang="en" class="${themeClass}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource}; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <style>
    * { box-sizing: border-box; }
    :root { --bg:#fff; --header:#e0e0e0; --border:#e0e0e0; --border-strong:#8d8d8d; --text:#161616; --text-2:#525252; --link:#0f62fe; --primary:#0f62fe; --primary-hover:#0050e6; --secondary:#393939; --secondary-hover:#474747; --hover:#e8e8e8; --selected:#e0e0e0; --focus:#0f62fe; --disabled:#c6c6c6; --tag-bg:#d0e2ff; --tag-text:#0043ce; --tip-bg:#393939; --tip-text:#fff; }
    html.theme-dark { --bg:#262626; --header:#393939; --border:#393939; --border-strong:#6f6f6f; --text:#f4f4f4; --text-2:#c6c6c6; --link:#78a9ff; --primary:#0f62fe; --primary-hover:#0050e6; --secondary:#6f6f6f; --secondary-hover:#5e5e5e; --hover:#333; --selected:#525252; --focus:#fff; --disabled:#6f6f6f; --tag-bg:#0043ce; --tag-text:#d0e2ff; --tip-bg:#f4f4f4; --tip-text:#161616; }
    html, body { width:100%; min-height:100%; margin:0; overflow:hidden; }
    body { min-height:100vh; display:grid; place-items:center; padding:16px; background:var(--vscode-editor-background); color:var(--text); font-family:'IBM Plex Sans','IBM Plex Sans KR','Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif; }
    .dialog { width:min(720px,calc(100vw - 32px)); max-height:calc(100vh - 32px); height:${cardHeight}; overflow:hidden; display:flex; flex-direction:column; border:1px solid var(--border-strong); box-shadow:0 2px 6px rgba(0,0,0,.3); border-radius:0; background:var(--bg); color:var(--text); }
    .dialog.admin-open { width:min(1040px,calc(100vw - 32px)); }
    .header { height:64px; flex:0 0 64px; min-width:0; display:flex; align-items:center; gap:12px; padding:16px 16px 0 24px; }
    .logo { width:32px; height:32px; flex:0 0 32px; border:1px solid var(--border); border-radius:4px; background:#fff; object-fit:contain; }
    .header-title { min-width:0; flex:0 1 auto; overflow:hidden; color:var(--text-2); font-size:12px; line-height:16px; letter-spacing:.32px; white-space:nowrap; text-overflow:ellipsis; }
    .unread-badge[hidden] { display:none; }
    .unread-badge { flex:0 0 auto; min-width:18px; height:18px; padding:0 6px; display:inline-flex; align-items:center; justify-content:center; border-radius:999px; background:var(--tag-bg); color:var(--tag-text); font-size:12px; line-height:16px; font-weight:600; }
    .close-button { width:32px; height:32px; flex:0 0 32px; margin-left:0; padding:6px; border:0; background:transparent; color:var(--text); cursor:pointer; }
    .admin-toggle { margin-left:auto; }
    .mark-all-read { margin-left:8px; padding:4px 8px; border:0; background:transparent; color:var(--link); font:inherit; cursor:pointer; white-space:nowrap; }
    .admin-label { margin-left:auto; padding:4px 10px; border-radius:999px; background:var(--header); color:var(--text); font-size:12px; font-weight:600; }
    .manage-users-groups { padding:6px 10px; border:1px solid var(--border-strong); background:transparent; color:var(--link); font:inherit; font-size:13px; cursor:pointer; white-space:nowrap; }
    .close-button svg { width:20px; height:20px; }
    .content { min-height:0; flex:1 1 auto; padding:16px 24px 8px; display:flex; flex-direction:column; }
    .content[hidden] { display:none; }
    .workspace { min-height:0; flex:1 1 auto; display:flex; overflow:hidden; }
    .workspace .content { min-width:0; }
    .admin-drawer { min-width:0; flex:1 1 auto; overflow:auto; padding:22px 32px; background:var(--bg); }
    .admin-drawer[hidden] { display:none; }
    .admin-layout { display:grid; grid-template-columns:minmax(300px, 40%) minmax(360px, 60%); gap:28px; max-width:940px; margin:0 auto; }
    .recipient-pane,.compose-pane { min-width:0; }
    .field { margin:0 0 16px; }
    .field label,.field-label { display:block; margin:0 0 8px; color:var(--text-2); font-size:14px; }
    .field input,.field textarea { width:100%; min-height:40px; padding:9px 12px; border:0; border-bottom:1px solid var(--border-strong); border-radius:0; background:var(--header); color:var(--text); font:inherit; }
    .field textarea { min-height:90px; resize:vertical; }
    .field input:focus,.field textarea:focus,.target-search:focus { outline:2px solid var(--focus); outline-offset:-2px; }
    .recipient-tabs { display:grid; grid-template-columns:repeat(3,1fr); margin-bottom:12px; border:1px solid var(--border-strong); }
    .recipient-tabs button { min-height:42px; border:0; background:var(--bg); color:var(--text); font:inherit; cursor:pointer; }
    .recipient-tabs button[aria-pressed="true"] { background:var(--text); color:var(--bg); }
    .target-search { width:100%; height:40px; margin:0 0 10px; padding:0 12px; border:0; background:var(--header); color:var(--text); font:inherit; }
    .target-list { max-height:196px; overflow:auto; border:1px solid var(--border); }
    .target-list[hidden] { display:none; }
    .target-row { width:100%; min-height:42px; display:flex; align-items:center; gap:10px; padding:8px 12px; border:0; border-bottom:1px solid var(--border); background:var(--bg); color:var(--text); text-align:left; font:inherit; }
    button.target-row { cursor:pointer; }
    .target-row:hover { background:var(--hover); }
    .target-row input { width:18px; height:18px; margin:0; accent-color:var(--text); }
    .radio-mark { width:18px; height:18px; flex:0 0 18px; border:1px solid var(--border-strong); border-radius:50%; }
    .group-row[aria-checked="true"] .radio-mark { border:5px solid var(--text); }
    .target-name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .target-meta { margin-left:auto; color:var(--text-2); font-size:12px; white-space:nowrap; }
    .selection-summary { margin:10px 0 0; color:var(--text-2); font-size:13px; }
    .selected-users { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
    .selected-chip { padding:5px 10px; border:0; border-radius:999px; background:var(--text); color:var(--bg); font:inherit; font-size:12px; cursor:pointer; }
    .warning { margin:12px 0; padding:12px 14px; border-left:4px solid #f1c21b; background:#fcf4d6; color:#393939; font-size:13px; line-height:19px; }
    .warning[hidden] { display:none; }
    .form-top-row { display:grid; grid-template-columns:minmax(130px, .8fr) minmax(200px, 1.2fr); gap:16px; }
    .character-count { margin-top:4px; color:var(--text-2); text-align:right; font-size:12px; }
    .preview-label { margin:8px 0; color:var(--text-2); font-size:13px; }
    .preview-row { min-height:54px; display:flex; align-items:center; gap:8px; overflow:hidden; padding:12px 16px; background:var(--header); color:var(--text-2); white-space:nowrap; }
    .preview-row strong { flex:0 0 auto; max-width:110px; overflow:hidden; color:var(--text); text-overflow:ellipsis; }
    .preview-row span { min-width:0; overflow:hidden; text-overflow:ellipsis; }
    .admin-back { border:0; background:transparent; color:var(--link); font:inherit; cursor:pointer; }
    .send-button { min-width:180px; height:48px; padding:0 20px; border:0; background:var(--primary); color:white; font:inherit; cursor:pointer; }
    .send-button:disabled { opacity:.55; cursor:not-allowed; }
    table { width:100%; border-collapse:collapse; table-layout:fixed; }
    th { height:40px; padding:0 16px; background:var(--header); color:var(--text); font-size:14px; line-height:18px; font-weight:600; letter-spacing:.16px; text-align:left; }
    th.link-heading { width:72px; padding:0; text-align:center; }
    th.time-heading { width:96px; padding:0; text-align:right; }
    td { height:40px; padding:0; border-bottom:1px solid var(--border); color:var(--text); }
    .message-select { width:100%; height:40px; min-width:0; display:flex; align-items:center; overflow:hidden; padding:0 16px; border:0; background:transparent; color:var(--text); text-align:left; font-family:inherit; font-size:14px; line-height:18px; letter-spacing:.16px; cursor:pointer; }
    .message-select strong { flex:0 0 auto; max-width:42%; overflow:hidden; color:var(--text); font-weight:600; text-overflow:ellipsis; white-space:nowrap; }
    .message-body { min-width:0; overflow:hidden; color:var(--text-2); text-overflow:ellipsis; white-space:nowrap; }
    tr.selected td { background:var(--selected); }
    tr[data-event-id]:hover:not(.selected) td { background:var(--hover); }
    .link-cell { width:72px; text-align:center; white-space:nowrap; }
    .link-button { min-width:32px; height:32px; display:inline-flex; align-items:center; justify-content:center; gap:3px; padding:0 4px; border:0; background:transparent; color:var(--link); cursor:pointer; }
    .link-button svg { width:16px; height:16px; }
    .link-button span { font-size:11px; font-weight:600; }
    .time-cell { width:96px; padding-right:0; color:var(--text-2); text-align:right; font-size:14px; line-height:18px; font-variant-numeric:tabular-nums; white-space:nowrap; }
    .empty { height:40px; padding:0 16px; color:var(--text-2); font-size:14px; }
    .pagination { min-height:40px; margin-top:8px; display:flex; align-items:center; justify-content:center; }
    .pagination ul { display:flex; align-items:center; justify-content:center; gap:0; margin:0; padding:0; list-style:none; }
    .pagination button { width:32px; height:32px; display:inline-flex; align-items:center; justify-content:center; padding:0 8px; border:0; border-bottom:4px solid transparent; background:transparent; color:var(--text-2); font-family:inherit; font-size:14px; line-height:18px; letter-spacing:.16px; cursor:pointer; }
    .pagination button[aria-current="page"] { border-bottom-color:var(--link); color:var(--text); font-weight:600; }
    .pagination button:disabled { color:var(--disabled); cursor:default; }
    .pagination .ellipsis { width:32px; height:32px; display:inline-flex; align-items:center; justify-content:center; color:var(--text-2); font-size:14px; }
    .footer { min-height:72px; flex:0 0 72px; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:16px 24px; border-top:1px solid var(--border); }
    .copy-action { min-width:128px; height:40px; display:inline-flex; align-items:center; justify-content:flex-start; gap:8px; padding:0 16px; border:0; background:transparent; color:var(--link); font-family:inherit; font-size:14px; line-height:18px; letter-spacing:.16px; cursor:pointer; }
    .copy-action svg { width:16px; height:16px; flex:0 0 16px; }
    .action-group { display:flex; gap:1px; }
    button.action { min-width:128px; height:40px; display:inline-flex; align-items:center; justify-content:center; padding:0 16px; border:0; border-radius:0; color:#fff; font-family:inherit; font-size:14px; line-height:18px; letter-spacing:.16px; cursor:pointer; }
    #confirm { background:var(--primary); }
    #confirm:hover { background:var(--primary-hover); }
    button:focus-visible, .message-select:focus-visible { outline:0; box-shadow:inset 0 0 0 2px var(--focus),inset 0 0 0 3px var(--bg); }
    .toast { position:absolute; z-index:5; top:16px; right:16px; max-width:calc(100% - 32px); padding:12px 16px; background:var(--tip-bg); color:var(--tip-text); box-shadow:0 2px 6px #0003; font-size:14px; line-height:18px; }
    .toast[hidden] { display:none; }
    @media (max-width:760px) { .dialog.admin-open { width:min(720px,calc(100vw - 24px)); } .admin-layout { grid-template-columns:1fr; gap:16px; } .admin-drawer { padding:16px; } }
    @media (max-width:600px) { .content { padding-right:12px; padding-left:12px; } .header { padding-left:12px; } .footer { padding-right:12px; padding-left:12px; gap:4px; } .action-group button.action { min-width:88px; } .time-cell, th.time-heading { width:78px; } .link-cell, th.link-heading { width:48px; } .mark-all-read { padding:4px 2px; font-size:12px; } .copy-action { min-width:auto; padding:0 8px; font-size:12px; } }
    @media (max-height:480px) { .header { height:52px; flex-basis:52px; padding-top:8px; } .content { padding-top:8px; } th,td,.message-select { height:36px; } .pagination { min-height:32px; margin-top:4px; } .footer { min-height:56px; flex-basis:56px; padding-top:8px; padding-bottom:8px; } }
  </style></head><body>
    <main class="dialog ${adminDrawerOpen ? "admin-open" : ""}" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabindex="-1">
      <header class="header">
        <img class="logo" src="${logoUri}" alt="IBM Bob" />
        <div class="header-title" id="dialog-title" title="${adminDrawerOpen ? "IBM Bob Notification > Send" : "IBM Bob Notification"}">${adminDrawerOpen ? "IBM Bob Notification > Send" : "IBM Bob Notification"}</div>
        ${adminDrawerOpen ? "" : badge}
        ${!adminDrawerOpen ? '<button class="mark-all-read" id="mark-all-read" type="button">Mark all as read</button>' : (adminConfig.isAdmin ? '<span class="admin-label">Admin</span>' : "")}
        ${adminDrawerOpen && adminConfig.isAdmin ? '<button class="manage-users-groups" id="manage-users-groups" type="button">Users & Groups</button>' : ""}
        ${adminConfig.isAdmin && !adminDrawerOpen ? '<button class="close-button admin-toggle" id="admin-toggle" type="button" aria-label="New notification" title="New notification"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v14M3 10h14" fill="none" stroke="currentColor" stroke-width="1.7"/></svg></button>' : ""}
        <button class="close-button" id="close" type="button" aria-label="Close" title="Close"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 4l12 12M16 4 4 16" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button>
      </header>
      <div class="workspace">
      <section class="content" aria-label="Notification messages" ${adminDrawerOpen ? "hidden" : ""}>
        <table aria-label="Received messages">
          <thead><tr><th scope="col">Message</th><th scope="col" class="link-heading">Link</th><th scope="col" class="time-heading">Received</th></tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
        ${pagination}
      </section>
      ${adminConfig.isAdmin ? `<section class="admin-drawer" id="admin-drawer" ${adminDrawerOpen ? "" : "hidden"} aria-label="New notification">
        <div class="admin-layout">
          <div class="recipient-pane">
            <span class="field-label">Recipients</span>
            <div class="recipient-tabs" role="group" aria-label="Recipient type">
              <button type="button" data-target-type="all" aria-pressed="${initialTargetType === "all"}">All</button>
              <button type="button" data-target-type="group" aria-pressed="${initialTargetType === "group"}">Groups</button>
              <button type="button" data-target-type="user" aria-pressed="${initialTargetType === "user"}">Individuals</button>
            </div>
            <div class="warning" id="all-warning">Sends to all ${adminConfig.employees.length} registered employees. This can't be recalled after it is sent.</div>
            <div id="group-selection" ${initialTargetType === "group" ? "" : "hidden"}>
              <input class="target-search" id="group-search" type="search" placeholder="Search groups">
              <div class="target-list" id="group-list" role="radiogroup" aria-label="Choose one group">${groupRows || '<p class="selection-summary">No groups are configured.</p>'}</div>
            </div>
            <div id="employee-selection" ${initialTargetType === "user" ? "" : "hidden"}>
              <input class="target-search" id="employee-search" type="search" placeholder="Search by employee no.">
              <div class="target-list" id="employee-list">${employeeRows || '<p class="selection-summary">No employees are configured.</p>'}</div>
              <div class="selected-users" id="selected-users"></div>
            </div>
            <p class="selection-summary" id="recipient-count" aria-live="polite"></p>
          </div>
          <div class="compose-pane">
            <div class="form-top-row">
              <div class="field"><label for="request-id">Request ID (optional)</label><input id="request-id" maxlength="64" placeholder="Request ID" value="${requestIdValue}"></div>
              <div class="field"><label for="link-url">Link (optional)</label><input id="link-url" type="url" placeholder="https://..." value="${linkUrlValue}"></div>
            </div>
            <div class="field"><label for="admin-message">Message</label><textarea id="admin-message" maxlength="200" placeholder="Write a notification (up to 200 characters)">${messageValue}</textarea><div class="character-count"><span id="message-count">${String(adminFormDraft.message || "").length}</span> / 200</div></div>
            <p class="preview-label">Preview — as shown in employees' notification popup</p>
            <div class="preview-row"><strong id="preview-id">${requestIdValue || "NOTICE"}</strong><span id="preview-message">${messageValue || "Your notification preview"}</span></div>
          </div>
        </div>
      </section>` : ""}
      </div>
      <footer class="footer">
        ${adminDrawerOpen ? '<button class="admin-back" id="admin-back" type="button">← &nbsp; Back to notifications</button><button class="send-button" id="admin-send" type="button">Send to <span id="send-count">0</span></button>' : '<button class="copy-action" id="copy" type="button"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 1h9v11H5V1ZM3 4H2v11h9v-1H3V4Z" fill="currentColor"/></svg><span>Copy Message</span></button><button class="action" id="confirm" type="button">Confirm</button>'}
      </footer>
      <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
    </main>
    <script nonce="${nonce}">
      const vscode = acquireVsCodeApi();
      const toast = document.getElementById('toast');
      let toastTimer;
      function parseDate(raw) {
        const compact = String(raw || '').match(/^(\\d{4})(\\d{2})(\\d{2})T(\\d{2})(\\d{2})(\\d{2})Z$/);
        if (compact) raw = compact[1]+'-'+compact[2]+'-'+compact[3]+'T'+compact[4]+':'+compact[5]+':'+compact[6]+'Z';
        const date = new Date(raw);
        return Number.isNaN(date.getTime()) ? null : date;
      }
      function relativeTime(raw) {
        const date = parseDate(raw); if (!date) return '—';
        const now = new Date(), minutes = Math.max(0, Math.floor((now-date)/60000));
        if (minutes < 1) return 'Just now';
        if (minutes < 60) return minutes+' min'+(minutes===1?'':'s')+' ago';
        const sameDay = (a,b) => a.getFullYear()===b.getFullYear() && a.getMonth()===b.getMonth() && a.getDate()===b.getDate();
        if (sameDay(date,now)) { const hours=Math.floor(minutes/60); return hours+' hr'+(hours===1?'':'s')+' ago'; }
        const yesterday = new Date(now); yesterday.setDate(now.getDate()-1);
        if (sameDay(date,yesterday)) return 'Yesterday';
        return date.toLocaleDateString('en-US',{month:'short',day:'numeric'});
      }
      function refreshRelativeTimes() {
        document.querySelectorAll('time[data-created-at]').forEach((node) => { node.textContent=relativeTime(node.dataset.createdAt); });
      }
      function showToast(message) {
        toast.textContent=message; toast.hidden=false; clearTimeout(toastTimer);
        toastTimer=setTimeout(() => { toast.hidden=true; },3000);
      }
      document.querySelector('.message-select')?.focus();
      document.querySelectorAll('.message-select').forEach((button) => button.addEventListener('click', () => {
        document.querySelectorAll('tr.selected').forEach((row) => row.classList.remove('selected'));
        const row=button.closest('tr'); row.classList.add('selected');
        document.querySelectorAll('.message-select').forEach((item) => item.setAttribute('aria-pressed','false'));
        button.setAttribute('aria-pressed','true');
        vscode.postMessage({command:'select', eventId:button.dataset.eventId});
      }));
      document.querySelectorAll('.pagination button[data-page]:not(:disabled)').forEach((button) => button.addEventListener('click', () => {
        vscode.postMessage({command:'page', page:Number(button.dataset.page)});
      }));
      document.querySelectorAll('.message-select').forEach((button) => button.addEventListener('dblclick', () => {
        vscode.postMessage({command:'copy', eventId:button.dataset.eventId, copyMessage:true, doubleClick:true});
      }));
      document.querySelectorAll('.link-button').forEach((button) => button.addEventListener('click', () => {
        try { vscode.postMessage({command:'openLinks', links:JSON.parse(button.dataset.links || '[]')}); }
        catch (error) { console.error('Invalid resource links', error); }
      }));
      document.getElementById('copy')?.addEventListener('click', () => {
        const selected=document.querySelector('.message-select[aria-pressed="true"]');
        if (selected) vscode.postMessage({command:'copy',eventId:selected.dataset.eventId,copyMessage:true});
      });
      document.getElementById('close').addEventListener('click', () => vscode.postMessage({command:'close'}));
      const adminForm=document.querySelector('#admin-drawer:not([hidden])');
      const groupSearch=document.getElementById('group-search');
      const employeeSearch=document.getElementById('employee-search');
      const groupRows=[...document.querySelectorAll('.group-row')];
      const employeeRows=[...document.querySelectorAll('.employee-row')];
      const requestId=document.getElementById('request-id');
      const adminMessage=document.getElementById('admin-message');
      const linkUrl=document.getElementById('link-url');
      let targetType=${safeScriptJson(initialTargetType)};
      let targetGroup=${safeScriptJson(adminFormDraft.targetGroup || "")};
      const selectedEmployees=new Set(${safeScriptJson(Array.from(selectedEmployeeNos))});
      const employees=${adminEmployeesJson};
      const groupCounts=${adminGroupCountsJson};
      const employeeGroups=${employeeGroupsJson};
      function saveAdminDraft() {
        if (!adminForm) return;
        adminFormDraftForSave();
      }
      function adminFormDraftForSave() {
        vscode.postMessage({command:'admin-draft',draft:{targetType,targetGroup,employeeNos:[...selectedEmployees],requestId:requestId.value,message:adminMessage.value,linkUrl:linkUrl.value}});
      }
      function updateRecipientUI() {
        if (!adminForm) return;
        document.querySelectorAll('[data-target-type]').forEach((button)=>button.setAttribute('aria-pressed',String(button.dataset.targetType===targetType)));
        document.getElementById('all-warning').hidden=targetType!=='all';
        document.getElementById('group-selection').hidden=targetType!=='group';
        document.getElementById('employee-selection').hidden=targetType!=='user';
        let count=targetType==='all'?employees.length:(targetType==='group'?Number(groupCounts[targetGroup]||0):selectedEmployees.size);
        const summary=document.getElementById('recipient-count');
        summary.textContent=targetType==='group'&&targetGroup?'Group "'+targetGroup+'" · '+count+' employees will receive this.':count+' employee'+(count===1?'':'s')+' will receive this.';
        document.getElementById('send-count').textContent=String(count);
        document.getElementById('admin-send').disabled=count===0||!adminMessage.value.trim();
        document.getElementById('message-count').textContent=String(adminMessage.value.length);
        document.getElementById('preview-id').textContent=requestId.value.trim()||'NOTICE';
        document.getElementById('preview-message').textContent=adminMessage.value.trim()||'Your notification preview';
        const selectedContainer=document.getElementById('selected-users');
        selectedContainer.replaceChildren();
        if(targetType==='user') for(const employee of selectedEmployees){
          const chip=document.createElement('button');chip.type='button';chip.className='selected-chip';chip.textContent=employee+' ×';chip.setAttribute('aria-label','Remove '+employee);
          chip.addEventListener('click',()=>{selectedEmployees.delete(employee);const checkbox=document.querySelector('.employee-check[value="'+CSS.escape(employee)+'"]');if(checkbox)checkbox.checked=false;updateRecipientUI();saveAdminDraft();});
          selectedContainer.appendChild(chip);
        }
      }
      function filterRows(input, rows, dataKey) {
        const term=input.value.trim().toLowerCase();
        rows.forEach((row)=>{row.hidden=!row.getAttribute(dataKey).includes(term);});
      }
      document.getElementById('admin-toggle')?.addEventListener('click',()=>vscode.postMessage({command:'admin-toggle',open:true}));
      document.getElementById('manage-users-groups')?.addEventListener('click',()=>vscode.postMessage({command:'manage-users-groups'}));
      document.getElementById('admin-back')?.addEventListener('click',()=>{saveAdminDraft();vscode.postMessage({command:'admin-toggle',open:false});});
      document.querySelectorAll('[data-target-type]').forEach((button)=>button.addEventListener('click',()=>{targetType=button.dataset.targetType;updateRecipientUI();saveAdminDraft();}));
      groupRows.forEach((button)=>button.addEventListener('click',()=>{targetGroup=button.dataset.group;groupRows.forEach((row)=>{const selected=row===button;row.setAttribute('aria-checked',String(selected));row.classList.toggle('checked',selected);});updateRecipientUI();saveAdminDraft();}));
      employeeRows.forEach((row)=>row.querySelector('.employee-check').addEventListener('change',(event)=>{const employee=event.target.value;if(event.target.checked)selectedEmployees.add(employee);else selectedEmployees.delete(employee);updateRecipientUI();saveAdminDraft();}));
      groupSearch?.addEventListener('input',()=>filterRows(groupSearch,groupRows,'data-search'));
      employeeSearch?.addEventListener('input',()=>filterRows(employeeSearch,employeeRows,'data-employee-row'));
      [requestId,adminMessage,linkUrl].filter(Boolean).forEach((node)=>node.addEventListener('input',()=>{updateRecipientUI();saveAdminDraft();}));
      updateRecipientUI();
      document.getElementById('admin-send')?.addEventListener('click',()=>vscode.postMessage({command:'admin-send',draft:{targetType,targetGroup,employeeNos:[...selectedEmployees],requestId:requestId.value.trim(),message:adminMessage.value.trim(),linkUrl:linkUrl.value.trim()}}));
      document.getElementById('mark-all-read')?.addEventListener('click', () => vscode.postMessage({command:'mark-all-read'}));
      document.getElementById('confirm')?.addEventListener('click', () => vscode.postMessage({command:'confirm'}));
      document.addEventListener('keydown',(event) => { if (event.key==='Escape') vscode.postMessage({command:'close'}); });
      window.addEventListener('message',(event) => {
        if (event.data?.type==='toast') showToast(event.data.message);
        if (event.data?.type==='unread-count') {
          const count=Number(event.data.count)||0, badge=document.getElementById('unread-badge');
          if (badge) {
            badge.textContent=count>99?'99+':String(count);
            badge.setAttribute('aria-label','Unread '+count);
            badge.hidden=count===0;
          }
        }
      });
      refreshRelativeTimes(); setInterval(refreshRelativeTimes,60000);
    </script>
  </body></html>`;
}

function updatePopup() {
  // Do not replace the composer DOM while its fields are being edited. The
  // current draft is reapplied when the admin returns to the notification list.
  if (notificationPanel && !adminDrawerOpen) renderPopupHtml(notificationPanel.webview);
}

function showNotificationPopup(context, preview = false) {
  popupPreview = preview;
  currentPage = 0;
  if (!notificationPanel) {
    output.appendLine("[popup_create] creating SR list webview popup");
    notificationPanel = vscode.window.createWebviewPanel(
      "itsmSrNotificationPopup",
      "IBM Bob Notification",
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, "media")],
      }
    );
    notificationPanel.onDidDispose(() => {
      output.appendLine("[popup_closed] SR list popup disposed");
      notificationPanel = undefined;
    }, null, context.subscriptions);
    notificationPanel.webview.onDidReceiveMessage(async (message) => {
      if (message.command === "copy") {
        const item = popupRows().find((row) => String(row.event_id) === String(message.eventId));
        if (!item) return;
        const copyMessage = Boolean(message.copyMessage || message.doubleClick);
        const copiedText = copyMessage ? copyTextForItem(item) : item.ticket_key;
        await vscode.env.clipboard.writeText(copiedText);
        if (message.doubleClick && String(item.event_id) !== "popup-test") {
          // A double-click both copies the same message as the footer action and marks only this SR read.
          readNotificationIds.add(String(item.event_id));
          await context.globalState.update(READ_NOTIFICATIONS_KEY, [...readNotificationIds]);
          updateNotificationStatus();
          output.appendLine(`[badge_update] unread=${getUnreadCount()} reason=double_click event_id=${item.event_id}`);
        }
        output.appendLine(`[popup_copy] ticket_key=${item.ticket_key} copy_message=${copyMessage}`);
        notificationPanel?.webview.postMessage({ type: "toast", message: "Message copied." });
      } else if (message.command === "openLinks") {
        const links = Array.isArray(message.links) ? message.links.filter((link) =>
          link && typeof link.title === "string" && typeof link.url === "string" && /^https?:\/\//i.test(link.url)
        ) : [];
        if (links.length) {
          try {
            const selected = links.length === 1 ? links[0] : await vscode.window.showQuickPick(
              links.map((link) => ({ label: link.title, description: new URL(link.url).host, url: link.url })),
              { placeHolder: "Choose a notification resource to open" }
            );
            if (selected?.url) await vscode.env.openExternal(vscode.Uri.parse(selected.url));
          } catch (error) {
            output.appendLine(`[popup_link_error] ${error?.stack || error}`);
          }
        }
      } else if (message.command === "admin-draft") {
        adminFormDraft = message.draft && typeof message.draft === "object" ? { ...message.draft } : {};
      } else if (message.command === "admin-toggle") {
        if (!adminConfig.isAdmin) return;
        adminDrawerOpen = Boolean(message.open);
        if (adminDrawerOpen && notificationPanel) renderPopupHtml(notificationPanel.webview);
        else updatePopup();
      } else if (message.command === "manage-users-groups") {
        if (!adminConfig.isAdmin) return;
        showUsersGroupsPanel(context);
      } else if (message.command === "admin-send") {
        if (!adminConfig.isAdmin) return;
        const draft = message.draft || {};
        adminFormDraft = { ...draft };
        const targetType = draft.targetType;
        const requestId = String(draft.requestId || "").trim();
        const messageText = String(draft.message || "").trim();
        const group = String(draft.targetGroup || "").trim();
        if (!messageText) {
          notificationPanel?.webview.postMessage({ type: "toast", message: "Enter a message before sending." });
          return;
        }
        if (messageText.length > 200 || requestId.length > 64) {
          notificationPanel?.webview.postMessage({ type: "toast", message: "Check the field length limits." });
          return;
        }
        const employeeNos = Array.isArray(draft.employeeNos) ? [...new Set(draft.employeeNos.map(String))] : [];
        if ((targetType === "group" && !adminConfig.groups.includes(group)) ||
            (targetType === "user" && (!employeeNos.length || employeeNos.some((item) => !adminConfig.employees.includes(item)))) ||
            !["all", "group", "user"].includes(targetType)) {
          notificationPanel?.webview.postMessage({ type: "toast", message: "Choose a valid recipient." });
          return;
        }
        const linkUrl = String(draft.linkUrl || "").trim();
        let links = [];
        if (linkUrl) {
          try {
            const url = new URL(linkUrl);
            if (!["http:", "https:"].includes(url.protocol)) throw new Error("HTTP(S) URL required");
            links = [{ title: url.host, url: url.toString() }];
          } catch {
            notificationPanel?.webview.postMessage({ type: "toast", message: "Enter a valid HTTP(S) link." });
            return;
          }
        }
        try {
          const token = await context.secrets.get(SECRET_KEY);
          const response = await fetch(`${getAdminBaseUrl()}/messages`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token || ""}`, "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
              target_type: targetType,
              target_group: targetType === "group" ? group : null,
              employee_no: null,
              employee_nos: targetType === "user" ? employeeNos : null,
              request_id: requestId,
              title: requestId || "Notification",
              message: messageText,
              links,
            }),
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(result.detail || result.error || `HTTP ${response.status}`);
          const count = Number(result.recipient_count || 0);
          adminFormDraft = {};
          adminDrawerOpen = false;
          updatePopup();
          notificationPanel?.webview.postMessage({ type: "toast", message: `Notification sent to ${count} recipient${count === 1 ? "" : "s"}.` });
          output.appendLine(`[admin_publish] request_id=${requestId} scope=${targetType} recipients=${count} event_id=${result.event_id}`);
        } catch (error) {
          notificationPanel?.webview.postMessage({ type: "toast", message: `Could not send notification: ${error.message}` });
          output.appendLine(`[admin_publish_error] ${error?.stack || error}`);
        }
      } else if (message.command === "select") {
        selectedEventId = message.eventId;
      } else if (message.command === "page") {
        const maxPage = Math.max(0, Math.ceil(popupRows().length / PAGE_SIZE) - 1);
        currentPage = Math.max(0, Math.min(Number(message.page) || 0, maxPage));
        selectedEventId = undefined;
        updatePopup();
      } else if (message.command === "mark-all-read") {
        for (const item of notificationItems) readNotificationIds.add(String(item.event_id));
        await context.globalState.update(READ_NOTIFICATIONS_KEY, [...readNotificationIds]);
        void syncReadReceipts(context, notificationItems);
        updateNotificationStatus();
        notificationPanel?.webview.postMessage({ type: "toast", message: "All notifications marked as read." });
        output.appendLine(`[badge_update] unread=${getUnreadCount()} reason=mark_all_read`);
      } else if (message.command === "confirm") {
        const visibleRows = popupRows().slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
        for (const item of visibleRows) {
          if (String(item.event_id) !== "popup-test") readNotificationIds.add(String(item.event_id));
        }
        await context.globalState.update(READ_NOTIFICATIONS_KEY, [...readNotificationIds]);
        void syncReadReceipts(context, visibleRows);
        updateNotificationStatus();
        output.appendLine(`[badge_update] unread=${getUnreadCount()} reason=confirm`);
        output.appendLine(`[popup_action] confirm marked_read=${visibleRows.filter((item) => String(item.event_id) !== "popup-test").length}`);
        notificationPanel?.dispose();
      } else if (message.command === "cancel" || message.command === "close") {
        output.appendLine(`[popup_action] ${message.command}`);
        notificationPanel?.dispose();
      }
    }, null, context.subscriptions);
  } else {
    notificationPanel.reveal(vscode.ViewColumn.Active, false);
  }
  renderPopupHtml(notificationPanel.webview);
  void refreshAdminConfig(context);
  output.appendLine(`[popup_show_called] item_count=${popupRows().length}`);
  return notificationPanel;
}

function runPopupSmokeTest(context) {
  try {
    output.appendLine("[popup_test] opening design preview popup");
    showNotificationPopup(context, true);
  } catch (error) {
    output.appendLine(`[popup_test_error] ${error?.stack || error}`);
    void vscode.window.showErrorMessage(`SR popup 테스트 실패: ${error.message}`);
  }
}

async function addNotification(context, payload, eventId) {
  if (notificationItems.some((item) => String(item.event_id) === String(eventId))) return;
  notificationItems.push({
    event_id: eventId,
    event_type: payload.event_type,
    notification_id: payload.notification_id,
    ticket_key: payload.ticket_key || "NOTICE",
    title: payload.title,
    message: payload.message,
    links: Array.isArray(payload.links) ? payload.links : [],
    service_name: payload.service_name,
    severity: payload.severity,
    status: payload.status,
    created_at: payload.created_at,
    url: payload.url || payload.link || payload.details_url || payload.detail_url || payload.service_request_url,
  });
  readNotificationIds.delete(String(eventId));
  notificationItems = notificationItems.slice(-MAX_NOTIFICATIONS);
  const retainedIds = new Set(notificationItems.map((item) => String(item.event_id)));
  readNotificationIds = new Set([...readNotificationIds].filter((id) => retainedIds.has(String(id))));
  await context.globalState.update(READ_NOTIFICATIONS_KEY, [...readNotificationIds]);
  currentPage = 0;
  selectedEventId = undefined;
  await context.globalState.update(NOTIFICATIONS_KEY, notificationItems);
  updateNotificationStatus();

  // Reuse the current custom popup and refresh the table, keeping newest SR first.
  if (!notificationPanel) {
    try {
      showNotificationPopup(context);
      output.appendLine(`[popup_opened] event_id=${eventId} ticket_key=${payload.ticket_key}`);
    } catch (error) {
      output.appendLine(`[popup_error] ${error?.stack || error}`);
    }
  } else {
    popupPreview = false;
    updatePopup();
    // Re-send after HTML refresh so the Webview receives the current value.
    updateNotificationStatus();
  }
  output.appendLine(`[badge_update] unread=${getUnreadCount()} reason=new_event event_id=${eventId}`);
  output.appendLine(`[notification_added] event_id=${eventId} ticket_key=${payload.ticket_key} total=${notificationItems.length}`);
}

/**
 * Start the listener once. The connection loop reconnects after network errors
 * and passes its latest event ID so events created while Bob was disconnected
 * can be replayed from the MySQL outbox.
 */
function startListener(context) {
  if (connectionTask) {
    output.show(true);
    output.appendLine("[start] listener is already running");
    void vscode.window.showInformationMessage("ITSM SR 알림 수신기가 이미 실행 중입니다.");
    return;
  }
  output.show(true);
  output.appendLine(`[start] ${new Date().toISOString()} listener start requested`);
  activeController = new AbortController();
  setStatus("$(sync~spin)", "ITSM SR 이벤트 피드에 연결 중입니다.");
  connectionTask = connectionLoop(context, activeController.signal)
    .catch((error) => {
      if (error?.name !== "AbortError") {
        output.appendLine(`[fatal] ${error?.stack || error}`);
        void vscode.window.showErrorMessage(`ITSM SR 알림 수신기를 시작하지 못했습니다: ${error.message}`);
      }
    })
    .finally(() => {
      connectionTask = undefined;
      activeController = undefined;
      setStatus("$(bell-slash)", "ITSM SR 알림 수신기가 중지되어 있습니다.");
    });
}

function stopListener() {
  if (!activeController) {
    void vscode.window.showInformationMessage("ITSM SR 알림 수신기가 실행 중이 아닙니다.");
    return;
  }
  activeController.abort();
  setStatus("$(bell-slash)", "ITSM SR 알림 수신기를 중지했습니다.");
}

async function connectionLoop(context, signal) {
  let retryDelayMs = 1000;

  while (!signal.aborted) {
    const token = await context.secrets.get(SECRET_KEY);
    if (!token) {
      setStatus("$(key)", "Bearer token을 설정해야 연결할 수 있습니다.");
      throw new Error("먼저 명령 팔레트에서 ‘IBM Bob Notifier: Set Bearer Token’을 실행하세요.");
    }

    const endpoint = getConfig().get("sseUrl");
    if (!endpoint) throw new Error("설정 ibmBobNotification.sseUrl 값이 비어 있습니다.");

    const cursor = normalizeEventId(context.globalState.get(CURSOR_KEY, "0"));
    const url = new URL(endpoint);
    url.searchParams.set("after_event_id", String(cursor));

    try {
      output.appendLine(`[connect_attempt] ${new Date().toISOString()} ${url.toString()}`);
      setStatus("$(sync~spin)", `연결 중: ${url.origin}`);
      await consumeEventStream(context, url, token, signal);
      retryDelayMs = 1000;
    } catch (error) {
      if (signal.aborted || error?.name === "AbortError") break;
      if (error?.status === 401 || error?.status === 403) throw error;
      output.appendLine(`[connection] ${new Date().toISOString()} ${error?.stack || error}`);
      setStatus("$(warning)", `연결이 끊겼습니다. ${Math.round(retryDelayMs / 1000)}초 후 다시 연결합니다.`);
      await delay(retryDelayMs, signal);
      retryDelayMs = Math.min(retryDelayMs * 2, 30000);
    }
  }
}

async function consumeEventStream(context, url, token, signal) {
  const cursor = normalizeEventId(context.globalState.get(CURSOR_KEY, "0"));
  const headers = {
    Accept: "text/event-stream",
    Authorization: `Bearer ${token}`,
  };
  if (BigInt(cursor) > 0n) headers["Last-Event-ID"] = cursor;

  const response = await fetch(url, { method: "GET", headers, signal });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    const error = new Error(`SSE endpoint returned HTTP ${response.status}. ${detail}`);
    error.status = response.status;
    throw error;
  }
  if (!response.body) throw new Error("SSE response has no body.");

  setStatus("$(radio-tower)", `수신 중: ${url.origin}`);
  output.appendLine(`[connected] ${url.toString()}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let event = newSseEvent();

  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) throw new Error("SSE connection closed by the server.");
      buffer += decoder.decode(value, { stream: true });

      let lineBreak;
      while ((lineBreak = buffer.indexOf("\n")) >= 0) {
        let line = buffer.slice(0, lineBreak);
        buffer = buffer.slice(lineBreak + 1);
        if (line.endsWith("\r")) line = line.slice(0, -1);

        if (line === "") {
          if (event.data.length > 0) {
            await handleSseEvent(context, event, signal);
          }
          event = newSseEvent();
          continue;
        }
        if (line.startsWith(":")) continue; // SSE heartbeat/comment

        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        let fieldValue = colon < 0 ? "" : line.slice(colon + 1);
        if (fieldValue.startsWith(" ")) fieldValue = fieldValue.slice(1);

        if (field === "event") event.type = fieldValue;
        else if (field === "data") event.data.push(fieldValue);
        else if (field === "id" && !fieldValue.includes("\0")) event.id = fieldValue;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
}

function newSseEvent() {
  return { type: "message", data: [], id: undefined };
}

function normalizeEventId(value) {
  const candidate = String(value ?? "0");
  if (!/^\d+$/.test(candidate)) return "0";
  try { return BigInt(candidate).toString(); }
  catch { return "0"; }
}

async function handleSseEvent(context, event, signal) {
  if (signal.aborted) return;
  const rawData = event.data.join("\n");

  if (event.type === "relay_error") {
    output.appendLine(`[relay_error] ${rawData}`);
    return;
  }
  if (event.type !== "service_request") return;

  let payload;
  try {
    payload = JSON.parse(rawData);
  } catch (error) {
    output.appendLine(`[invalid-event] ${error.message}: ${rawData}`);
    return;
  }

  const eventId = normalizeEventId(event.id || payload.event_id);
  const validEventId = BigInt(eventId) > 0n;
  if (validEventId) {
    // Cursor updates for every event, including status changes, prevent replay loops.
    await context.globalState.update(CURSOR_KEY, eventId);
  }

  // Log receipt before displaying the toast so a pending/dismissed notification
  // cannot make the Output channel look as if the event was never received.
  output.appendLine(
    `[event_received] event_id=${validEventId ? eventId : "unknown"} ` +
    `event_type=${payload.event_type || "unknown"} ticket_key=${payload.ticket_key || "unknown"}`
  );

  // Open a popup for new SRs and general notifications. Other SR updates only advance the cursor.
  if (!new Set(["service_request.created", "notification.created"]).has(payload.event_type)) {
    output.appendLine(`[event_ignored] event_type=${payload.event_type || "unknown"}`);
    return;
  }

  await addNotification(context, payload, validEventId ? eventId : normalizeEventId(payload.event_id));
}

function delay(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const timer = setTimeout(resolve, milliseconds);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}

async function activate(context) {
  extensionContext = context;
  output = vscode.window.createOutputChannel("IBM Bob Notifier");
  output.appendLine(`[activate] IBM Bob Notifier version=${require("./package.json").version}`);
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 20);
  statusBar.command = "ibmBobNotification.start";
  notificationStatusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 19);
  notificationStatusBar.command = "itsmSrNotifier.openNotifications";
  notificationItems = context.globalState.get(NOTIFICATIONS_KEY, []);
  readNotificationIds = new Set(context.globalState.get(READ_NOTIFICATIONS_KEY, []));
  context.subscriptions.push(output, statusBar, notificationStatusBar);
  context.subscriptions.push(vscode.window.onDidChangeActiveColorTheme(() => updatePopup()));
  updateNotificationStatus();
  setStatus("$(bell-slash)", "ITSM SR 알림 수신기가 중지되어 있습니다. 클릭하거나 명령 팔레트에서 Start를 실행하세요.");

  context.subscriptions.push(
    vscode.commands.registerCommand("ibmBobNotification.start", () => startListener(context)),
    vscode.commands.registerCommand("itsmSrNotifier.stop", stopListener),
    vscode.commands.registerCommand("itsmSrNotifier.openNotifications", () => {
      try {
        showNotificationPopup(context);
      } catch (error) {
        output.appendLine(`[popup_error] ${error?.stack || error}`);
        void vscode.window.showErrorMessage(`SR 알림 popup 표시 실패: ${error.message}`);
      }
    }),
    vscode.commands.registerCommand("itsmSrNotifier.testPopup", () => runPopupSmokeTest(context)),
    vscode.commands.registerCommand("itsmSrNotifier.clearNotifications", async () => {
      notificationItems = [];
      readNotificationIds.clear();
      popupPreview = false;
      await context.globalState.update(NOTIFICATIONS_KEY, notificationItems);
      await context.globalState.update(READ_NOTIFICATIONS_KEY, []);
      updateNotificationStatus();
      updatePopup();
      updateNotificationStatus();
      output.appendLine("[badge_update] unread=0 reason=clear");
      void vscode.window.showInformationMessage("SR 알림 목록을 비웠습니다.");
    }),
    vscode.commands.registerCommand("itsmSrNotifier.setToken", async () => {
      const token = await vscode.window.showInputBox({
        title: "IBM Bob Notifier Bearer Token",
        prompt: "ITSM_EVENT_USER_TOKENS_JSON에서 이 Bob 담당자(employee_no)에 매핑한 token 값만 입력하세요. Bearer 접두사는 제외합니다.",
        password: true,
        ignoreFocusOut: true,
      });
      if (!token) return;
      await context.secrets.store(SECRET_KEY, token.trim());
      output.show(true);
      output.appendLine(`[token] ${new Date().toISOString()} user token stored in SecretStorage`);
      void vscode.window.showInformationMessage("ITSM SR 알림 Bearer token을 안전하게 저장했습니다.");
      if (getConfig().get("autoStart", false)) startListener(context);
    }),
    vscode.commands.registerCommand("itsmSrNotifier.resetCursor", async () => {
      await context.globalState.update(CURSOR_KEY, 0);
      void vscode.window.showInformationMessage("이벤트 cursor를 초기화했습니다. 다음 연결에서 보관된 SR 이벤트를 다시 받습니다.");
    }),
  );

  if (getConfig().get("autoStart", false)) startListener(context);
}

function deactivate() {
  if (activeController) activeController.abort();
}

module.exports = { activate, deactivate };
