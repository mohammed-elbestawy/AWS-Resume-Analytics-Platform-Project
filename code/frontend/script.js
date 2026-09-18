const API_URL = "PASTE_YOUR_INVOKE_URL_HERE";

document.getElementById('resume-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('submit-btn');
  const statusBox = document.getElementById('status');

  const payload = {
    candidate_name: candidate_name.value,
    candidate_email: candidate_email.value,
    job_id: job_id.value,
    resume_text: resume_text.value,
  };

  btn.disabled = true;
  btn.textContent = "Submitting...";

  try {
    const res = await fetch(`${API_URL}/submit-resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    statusBox.className = res.ok ? "status success" : "status error";
    statusBox.textContent = res.ok ? data.message : data.error;
    if (res.ok) document.getElementById('resume-form').reset();
  } catch (err) {
    statusBox.className = "status error";
    statusBox.textContent = "Failed to submit. Please try again.";
  } finally {
    btn.disabled = false;
    btn.textContent = "Submit";
  }
});
