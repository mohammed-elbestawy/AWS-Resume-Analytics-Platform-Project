const API_URL   = "https://l9x975e8o7.execute-api.eu-north-1.amazonaws.com/prod";
const POOL_DATA = {
  UserPoolId: "PASTE_USER_POOL_ID",
  ClientId:   "PASTE_CLIENT_ID",
};

const userPool = new AmazonCognitoIdentity.CognitoUserPool(POOL_DATA);

document.getElementById("login-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const btn = document.getElementById("login-btn");
  const statusBox = document.getElementById("login-status");
  btn.disabled = true;

  const authDetails = new AmazonCognitoIdentity.AuthenticationDetails({
    Username: username.value,
    Password: password.value,
  });

  const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
    Username: username.value,
    Pool: userPool,
  });

  cognitoUser.authenticateUser(authDetails, {
    onSuccess: (session) => showDashboard(session.getIdToken().getJwtToken()),
    onFailure: (err) => {
      statusBox.className = "status error";
      statusBox.textContent = err.message || "Login failed.";
      btn.disabled = false;
    },
  });
});

document.getElementById("logout-btn").addEventListener("click", () => location.reload());

async function showDashboard(idToken) {
  document.getElementById("login-card").style.display = "none";
  document.getElementById("dashboard-card").style.display = "block";

  const res = await fetch(`${API_URL}/evaluations`, { headers: { Authorization: idToken } });
  const data = await res.json();
  document.getElementById("count").textContent = data.count;
  renderCandidates(data.candidates);
}

function renderCandidates(list) {
  const table = document.getElementById("candidates-table");
  if (!list.length) { table.innerHTML = "<p>No candidates yet.</p>"; return; }

  const rows = list.map(c => `
    <tr>
      <td>${esc(c.candidate_name)}</td>
      <td>${esc(c.candidate_email)}</td>
      <td>${esc(c.job_title)}</td>
      <td><b>${c.match_score}%</b></td>
      <td>${esc((c.missing_skills || []).join(", "))}</td>
    </tr>`).join("");

  table.innerHTML = `<table>
    <thead><tr><th>Name</th><th>Email</th><th>Job</th><th>Score</th><th>Missing Skills</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function esc(str) {
  const d = document.createElement("div");
  d.textContent = str ?? "";
  return d.innerHTML;
}
