// Admin sidebar functionality

// Toggle sidebar for mobile/tablet - make globally accessible
window.toggleSidebar = function() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (sidebar) sidebar.classList.toggle('active');
    if (overlay) overlay.classList.toggle('active');
};

// Close sidebar when clicking overlay or pressing Escape
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('sidebar-overlay')) {
        window.toggleSidebar();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && sidebar.classList.contains('active')) {
            window.toggleSidebar();
        }
    }
});

// Fetch current user info and update sidebar profile

async function loadCurrentUser() {
  const token = localStorage.getItem("token");
  if (!token) return;

  try {
    const resp = await fetch("/auth/me", {
      headers: { "Authorization": `Bearer ${token}` }
    });

    if (!resp.ok) {
      if (resp.status === 401) {
        localStorage.removeItem("token");
        window.location = "/ui/admin/login";
      }
      return;
    }

    const user = await resp.json();

    // Update sidebar profile
    const profileName = document.getElementById("sidebar-profile-name");
    const profileEmail = document.getElementById("sidebar-profile-email");

    if (profileName) {
      profileName.textContent = user.name || (window.I18N ? I18N.t('staff_admin') : "Administrator");
    }

    if (profileEmail) {
      profileEmail.textContent = user.email || (window.I18N ? I18N.t('logged_in') : "Logged In");
    }
  } catch (error) {
    console.error("Failed to load user info:", error);
  }
}

// Show change password modal
function showChangePasswordModal() {
  const modal = document.getElementById("changePasswordModal");
  if (modal) {
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
  }
}

// Handle change password form submission
async function handleChangePassword(event) {
  event.preventDefault();

  const currentPassword = document.getElementById("currentPassword").value;
  const newPassword = document.getElementById("newPassword").value;
  const confirmPassword = document.getElementById("confirmPassword").value;

  const errorDiv = document.getElementById("passwordError");
  const successDiv = document.getElementById("passwordSuccess");

  // Hide previous messages
  if (errorDiv) errorDiv.style.display = "none";
  if (successDiv) successDiv.style.display = "none";

  // Validate new password
  if (newPassword.length < 6) {
    if (errorDiv) {
      errorDiv.textContent = (window.I18N ? I18N.t('pwd_min_length') : "New password must be at least 6 characters");
      errorDiv.style.display = "block";
    }
    return;
  }

  if (newPassword !== confirmPassword) {
    if (errorDiv) {
      errorDiv.textContent = (window.I18N ? I18N.t('pwd_mismatch') : "New passwords do not match");
      errorDiv.style.display = "block";
    }
    return;
  }

  const token = localStorage.getItem("token");
  if (!token) {
    window.location = "/ui/admin/login";
    return;
  }

  try {
    const resp = await fetch("/auth/change-password", {
      method: "PUT",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      })
    });

    const data = await resp.json();

    if (!resp.ok) {
      if (errorDiv) {
        errorDiv.textContent = data.detail || (window.I18N ? I18N.t('pwd_change_failed') : "Failed to change password");
        errorDiv.style.display = "block";
      }
      return;
    }

    // Success
    if (successDiv) {
      successDiv.textContent = (window.I18N ? I18N.t('pwd_change_success') : "Password changed successfully!");
      successDiv.style.display = "block";
    }

    // Clear form
    document.getElementById("changePasswordForm").reset();

    // Close modal after 2 seconds
    setTimeout(() => {
      const modal = bootstrap.Modal.getInstance(document.getElementById("changePasswordModal"));
      if (modal) modal.hide();
    }, 2000);

  } catch (error) {
    console.error("Error changing password:", error);
    if (errorDiv) {
      errorDiv.textContent = (window.I18N ? I18N.t('network_error') : "Network error. Please try again.");
      errorDiv.style.display = "block";
    }
  }
}

// Initialize sidebar on page load
document.addEventListener("DOMContentLoaded", () => {
  loadCurrentUser();

  // Attach change password form handler
  const changePasswordForm = document.getElementById("changePasswordForm");
  if (changePasswordForm) {
    changePasswordForm.addEventListener("submit", handleChangePassword);
  }

  // Attach profile dropdown click handlers
  const changePasswordBtn = document.getElementById("changePasswordBtn");
  if (changePasswordBtn) {
    changePasswordBtn.addEventListener("click", showChangePasswordModal);
  }
});
