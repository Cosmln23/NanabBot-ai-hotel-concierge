// Lightweight frontend-only i18n helper (EN default, EN/TH supported)
// Usage: add data-i18n="key" or data-i18n-placeholder="key" on elements.
// Call I18N.apply() after DOM load; use I18N.t(key) in scripts for dynamic content.
const translations = {
  brand_name: {
    en: "AI Hotel Suite",
  },
  btn_add: {
    en: "Add",
  },
  btn_back: {
    en: "Back",
  },
  btn_cancel: {
    en: "Cancel",
  },
  btn_close: {
    en: "Close",
  },
  btn_confirm: {
    en: "Confirm",
  },
  btn_delete: {
    en: "Delete",
  },
  btn_edit: {
    en: "Edit",
  },
  btn_next: {
    en: "Next",
  },
  btn_refresh: {
    en: "Refresh",
  },
  btn_save: {
    en: "Save",
  },
  btn_search: {
    en: "Search",
  },
  btn_test_connection: {
    en: "Test Connection",
  },
  btn_testing: {
    en: "Testing...",
  },
  btn_saving: {
    en: "Saving...",
  },
  btn_done: {
    en: "Done",
  },
  line_test_saved: {
    en: "Connected & Saved!",
  },
  btn_upload: {
    en: "Upload file",
  },
  btn_clear: {
    en: "Clear",
  },
  confirm_clear: {
    en: "Are you sure you want to clear this?",
  },
  cleared_success: {
    en: "Cleared successfully",
  },
  file_choose: {
    en: "Choose file",
  },
  file_none: {
    en: "No file chosen",
  },
  change_password: {
    en: "Change Password",
  },
  chk_use_emojis: {
    en: "Use emojis",
  },
  chk_use_llm: {
    en: "Use LLM Agent",
  },
  completed: {
    en: "Completed",
  },
  configure: {
    en: "Configure",
  },
  confirm_delete: {
    en: "Are you sure you want to delete?",
  },
  confirm_password: {
    en: "Confirm New Password",
  },
  conv_active: {
    en: "Active Conversations",
  },
  conv_checkin: {
    en: "Check-in",
  },
  conv_checkout: {
    en: "Check-out",
  },
  conv_detail_title: {
    en: "Conversation Details",
  },
  conv_empty: {
    en: "No conversations found",
  },
  pagination_showing: {
    en: "Showing",
  },
  pagination_of: {
    en: "of",
  },
  pagination_prev: {
    en: "Previous",
  },
  pagination_next: {
    en: "Next",
  },
  conv_guest: {
    en: "Guest",
  },
  conv_guest_info: {
    en: "Guest Information",
  },
  conv_guest_generic: {
    en: "Guest",
  },
  conv_room_label: {
    en: "Room",
  },
  conv_on_hold: {
    en: "On Hold",
  },
  conv_related_tasks: {
    en: "Related Tasks",
  },
  conv_take_control: {
    en: "Take Control",
  },
  conv_return_ai: {
    en: "Return to AI",
  },
  conv_bot_paused: {
    en: "Bot paused",
  },
  conv_info_created: {
    en: "Created",
  },
  conv_info_guest_id: {
    en: "Guest ID",
  },
  conv_info_handler: {
    en: "Handler",
  },
  conv_info_status: {
    en: "Status",
  },
  conv_info_stay_id: {
    en: "Stay ID",
  },
  conv_info_title: {
    en: "Conversation Info",
  },
  conv_info_updated: {
    en: "Updated",
  },
  conv_loading: {
    en: "Loading conversations...",
  },
  conv_messages: {
    en: "Messages",
  },
  conv_msg_bot: {
    en: "Bot",
  },
  conv_msg_guest: {
    en: "Guest",
  },
  conv_no_messages: {
    en: "No messages yet",
  },
  conv_no_tasks: {
    en: "No related tasks",
  },
  conv_phone: {
    en: "Phone",
  },
  conv_room: {
    en: "Room",
  },
  conv_msg_staff: {
    en: "Staff",
  },
  conv_header_summary: {
    en: "ID: #{id} • {hotel} • {guest} • Room {room}",
  },
  conv_toggle_failed: {
    en: "Failed to toggle",
  },
  conv_send_failed: {
    en: "Failed to send",
  },
  conv_search_ph: {
    en: "Search conversations...",
  },
  conv_status_active: {
    en: "Active",
  },
  conv_subtitle: {
    en: "Monitor guest interactions and bot responses.",
  },
  conv_title: {
    en: "Conversations",
  },
  conv_view: {
    en: "View",
  },
  critical_active_label: {
    en: "Active",
  },
  critical_completed_label: {
    en: "Completed",
  },
  critical_title: {
    en: "Critical Alerts",
  },
  current_password: {
    en: "Current Password",
  },
  dashboard: {
    en: "Dashboard",
  },
  dashboard_title_owner: {
    en: "Owner Dashboard",
  },
  deleting: {
    en: "Deleting...",
  },
  empty: {
    en: "No tasks found",
  },
  error: {
    en: "Error",
  },
  filter_room_ph: {
    en: "e.g., 716",
  },
  filter_search_ph: {
    en: "Search summary...",
  },
  int_load_failed: {
    en: "Failed to load integrations",
  },
  int_pms_api_key: {
    en: "API Key",
  },
  int_pms_api_key_ph: {
    en: "Paste API key",
  },
  int_pms_none: {
    en: "None",
  },
  int_pms_property_id: {
    en: "Property ID",
  },
  int_pms_property_id_ph: {
    en: "Property ID",
  },
  int_pms_manage: {
    en: "Manage PMS connection",
  },
  int_locked: {
    en: "Locked",
  },
  int_unlock: {
    en: "Unlock",
  },
  int_save_pms: {
    en: "Save PMS Settings",
  },
  int_pms_section: {
    en: "PMS Configuration",
  },
  int_pms_type: {
    en: "PMS Type",
  },
  int_save_failed: {
    en: "Failed to save integrations",
  },
  int_saved: {
    en: "Saved",
  },
  int_status_configured: {
    en: "Configured",
  },
  int_pms_pro_only: {
    en: "PMS integration is available only for PRO tier",
  },
  int_upgrade_to_pro: {
    en: "Upgrade to PRO to enable PMS",
  },
  int_status_not_configured: {
    en: "Not configured",
  },
  int_msg_section: {
    en: "Messaging Provider",
  },
  int_msg_status_platform: {
    en: "Active (Platform Managed)",
  },
  int_msg_status_custom: {
    en: "Active (Custom Configuration)",
  },
  int_msg_status_disconnected: {
    en: "Disconnected",
  },
  int_msg_detail_platform: {
    en: "This channel uses platform default credentials. No action required.",
  },
  int_msg_detail_custom: {
    en: "Connected via custom credentials.",
  },
  int_msg_detail_none: {
    en: "No credentials set.",
  },
  int_locked_by_owner: {
    en: "Locked by owner",
  },
  int_platform_default: {
    en: "Platform Default",
  },
  int_show_qr: {
    en: "Show QR Code",
  },
  int_download_print: {
    en: "Download / Print",
  },
  int_qr_instruction: {
    en: "Place this QR code at reception or in rooms for guests to scan.",
  },
  int_room_qr_title: {
    en: "Room QR Generator",
  },
  int_room_qr_subtitle: {
    en: "Generate room-specific QR codes.",
  },
  int_room_qr_start: {
    en: "Start room",
  },
  int_room_qr_start_ph: {
    en: "e.g. 101",
  },
  int_room_qr_end: {
    en: "End room",
  },
  int_room_qr_end_ph: {
    en: "e.g. 120",
  },
  int_room_qr_generate: {
    en: "Generate",
  },
  int_room_qr_print: {
    en: "Print",
  },
  int_room_qr_hint: {
    en: "Print and place the correct QR in each room.",
  },
  int_room_qr_line_only: {
    en: "This feature only works with LINE messaging. WhatsApp does not require room QR codes as guests are identified automatically by phone number.",
  },
  int_room_qr_whatsapp_hint: {
    en: "Guests scan QR code to open WhatsApp chat with pre-filled room number.",
  },
  int_room_qr_line_hint: {
    en: "Guests scan QR code to open LINE chat with pre-filled room number.",
  },
  int_room_qr_no_phone: {
    en: "WhatsApp phone number not configured.",
  },
  int_room_qr_fetch_failed: {
    en: "Failed to generate LINE room QR codes.",
  },
  int_room_qr_invalid_range: {
    en: "Please enter a valid room range.",
  },
  int_room_qr_lib_missing: {
    en: "QR library not loaded.",
  },
  int_room_qr_room: {
    en: "Room",
  },
  int_room_qr_connect: {
    en: "Connect Room",
  },
  int_configure: {
    en: "Configure",
  },
  int_configure_messaging: {
    en: "Configure Messaging",
  },
  int_provider: {
    en: "Provider",
  },
  int_wa_byon_coming_soon: {
    en: "Custom WhatsApp Integration: Coming Soon",
  },
  int_wa_byon_coming_soon_desc: {
    en: "Currently using shared platform number. Bring Your Own Number (BYON) integration will be available in a future update.",
  },
  int_pms_coming_soon: {
    en: "Coming Soon",
  },
  int_whatsapp_credentials: {
    en: "WhatsApp Credentials",
  },
  int_phone_id: {
    en: "Phone Number ID",
  },
  int_phone_id_ph: {
    en: "whatsapp phone id",
  },
  int_access_token: {
    en: "Access Token",
  },
  int_access_token_ph: {
    en: "Paste access token",
  },
  int_waba_id: {
    en: "WABA ID",
  },
  int_waba_id_ph: {
    en: "Business Account ID",
  },
  int_line_credentials: {
    en: "LINE Credentials",
  },
  int_channel_secret: {
    en: "Channel Secret",
  },
  int_channel_secret_ph: {
    en: "Channel Secret",
  },
  int_channel_access_token: {
    en: "Channel Access Token",
  },
  int_channel_access_token_ph: {
    en: "Channel Access Token",
  },
  int_line_webhook_config: {
    en: "Webhook Configuration",
  },
  int_line_webhook_hint: {
    en: "Copy this URL to LINE Developers Console → Messaging API → Webhook settings",
  },
  int_webhook_url: {
    en: "Webhook URL",
  },
  int_wa_webhook_config: {
    en: "Webhook Configuration",
  },
  int_wa_webhook_hint: {
    en: "Copy these values to Meta Business Suite > WhatsApp > Configuration",
  },
  int_verify_token: {
    en: "Verify Token",
  },
  int_verify_token_hint: {
    en: "Auto-generated when you save credentials",
  },
  int_leave_empty_hint: {
    en: "Leave empty to keep current value",
  },
  pms_fill_all_fields: {
    en: "Please fill all PMS fields first",
  },
  int_pin_required: {
    en: "PIN required",
  },
  int_pin_incorrect: {
    en: "Incorrect PIN",
  },
  int_verify_password: {
    en: "Verify Password",
  },
  int_password_required_hint: {
    en: "Enter your login password to access this section.",
  },
  int_your_password: {
    en: "Your Password",
  },
  int_password_placeholder: {
    en: "Enter password",
  },
  int_go_back: {
    en: "Go Back",
  },
  int_password_required: {
    en: "Password is required",
  },
  int_password_incorrect: {
    en: "Incorrect password",
  },
  int_protected_page: {
    en: "This page is protected",
  },
  // Trial banner translations
  trial_banner_text: {
    en: "Trial:",
  },
  trial_days_remaining: {
    en: "days remaining",
  },
  trial_upgrade_btn: {
    en: "Upgrade to Basic - €29/mo",
  },
  trial_upgrade_pro_btn: {
    en: "Upgrade to PRO",
    ro: "Treci la PRO",
    th: "อัปเกรดเป็น PRO"
  },
  trial_expired_title: {
    en: "Trial Expired!",
  },
  trial_expired_msg: {
    en: "Your bot is paused. Upgrade to continue.",
  },
  trial_upgrade_now: {
    en: "Upgrade Now",
  },
  upgrade_now: {
    en: "Upgrade Now",
  },
  trial_expired_text: {
    en: "Trial expired! Your bot is stopped. Upgrade to continue.",
  },
  int_locked_pin_first: {
    en: "Locked. Unlock with PIN first.",
  },
  int_fetch_line_qr_failed: {
    en: "Failed to fetch LINE QR code.",
  },
  int_switch_platform_success: {
    en: "Switched to platform default.",
  },
  int_switch_platform_failed: {
    en: "Failed to switch to platform default",
  },
  int_pms_save_success: {
    en: "PMS Settings Saved",
  },
  int_pms_save_failed: {
    en: "Failed to save PMS settings",
  },
  int_close: {
    en: "Close",
  },
  int_save: {
    en: "Save",
  },
  int_line_qr_title: {
    en: "LINE QR Code",
  },
  int_pin_title: {
    en: "Enter Security PIN",
  },
  int_owner_pin: {
    en: "Owner PIN",
  },
  int_pin_placeholder: {
    en: "4-digit PIN",
  },
  int_wa_required: {
    en: "Phone Number ID and Access Token are required for custom WhatsApp.",
  },
  int_line_required: {
    en: "LINE requires Channel Secret and Access Token.",
  },
  int_cloudbeds_auth_method: {
    en: "Authentication Method",
  },
  int_auth_api_key: {
    en: "API Key (Recommended)",
  },
  int_auth_oauth: {
    en: "OAuth 2.0",
  },
  int_cloudbeds_api_key_ph: {
    en: "Paste API key from Cloudbeds",
  },
  int_cloudbeds_api_key_hint: {
    en: "Get your API key from Cloudbeds: Settings → Integrations → API",
  },
  int_cloudbeds_oauth_note: {
    en: "OAuth requires platform registration with Cloudbeds. Use API Key if you don't have OAuth credentials.",
  },
  int_cloudbeds_oauth_info: {
    en: "Cloudbeds uses OAuth 2.0. Click the button below to connect your property.",
  },
  int_configure_pms: {
    en: "Configure PMS",
  },
  int_connect_cloudbeds: {
    en: "Connect Cloudbeds",
  },
  int_connected: {
    en: "Connected",
  },
  int_disconnect: {
    en: "Disconnect",
  },
  int_cloudbeds_disconnected: {
    en: "Cloudbeds disconnected successfully.",
  },
  int_cloudbeds_connected_success: {
    en: "Cloudbeds connected successfully!",
  },
  integrations_subtitle: {
    en: "Manage external connections and APIs.",
  },
  integrations_title: {
    en: "Integrations",
  },
  lang_en: {
    en: "🇬🇧 English",
  },
  lang_ro: {
    en: "🇷🇴 Romanian",
  },
  lang_th: {
    en: "🇹🇭 ไทย",
  },
  lbl_additional_notes: {
    en: "Additional notes",
  },
  lbl_welcome_text: {
    en: "Welcome message",
  },
  lbl_welcome_text_ph: {
    en: "Example: Welcome! I'm here if you need anything.",
  },
  welcome_text_hint: {
    en: "Used for LINE after connecting and for WhatsApp welcome message. Leave empty to use default.",
  },
  lbl_bilingual_welcome: {
    en: "Also send in English",
  },
  bilingual_welcome_hint: {
    en: "If enabled, sends a second message in English after the main welcome message.",
  },
  default_welcome_msg: {
    en: "Good day, I'm {bot_name}, the virtual assistant of {hotel_name}. You are in room {room}. I can assist you with: WiFi, breakfast, check-in/out, parking, housekeeping. How may I help?",
  },
  default_msg_label: {
    en: "Default message:",
  },
  lbl_bot_name: {
    en: "Bot name",
  },
  lbl_bot_name_ph: {
    en: "e.g., Mali from Reception",
  },
  lbl_breakfast: {
    en: "Breakfast hours",
  },
  lbl_breakfast_ph: {
    en: "e.g., 07:30-10:00",
  },
  lbl_checkin: {
    en: "Check-in time",
  },
  lbl_checkin_ph: {
    en: "e.g., 14:00",
  },
  lbl_checkout: {
    en: "Check-out time",
  },
  lbl_checkout_ph: {
    en: "e.g., 12:00",
  },
  lbl_escalation_msg: {
    en: "Escalation message",
  },
  lbl_escalation_msg_ph: {
    en: "Message shown when escalating to human",
  },
  lbl_extract_preview: {
    en: "Extracted text (preview)",
  },
  lbl_guest_lang: {
    en: "Guest languages",
  },
  lbl_guest_lang_ph: {
    en: "auto (auto-detect)",
  },
  lbl_hotel_rules: {
    en: "Hotel Rules",
  },
  lbl_locked_owner: {
    en: "Locked by owner",
  },
  lbl_max_repeat: {
    en: "Max repeated answers",
  },
  lbl_parking: {
    en: "Parking policy",
  },
  lbl_parking_ph: {
    en: "e.g., Free parking available",
  },
  lbl_products_hint: {
    en: "Official list of products/services and prices",
  },
  lbl_products_ph: {
    en: "e.g.:\nWater 500ml - 20 THB\nCoffee - 60 THB",
  },
  lbl_repeat_policy: {
    en: "Repeat policy",
  },
  lbl_repeat_policy_ph: {
    en: "What the bot does when repeating answers",
  },
  lbl_staff_lang: {
    en: "Staff language",
  },
  lbl_staff_lang_ph: {
    en: "en, th",
  },
  lbl_tone: {
    en: "Tone",
  },
  tone_friendly: {
    en: "friendly",
  },
  tone_professional: {
    en: "professional",
  },
  tone_hint: {
    en: "Affects bot responses and welcome message style",
  },
  lbl_welcome_preview: {
    en: "Welcome Message Preview",
  },
  welcome_preview_hint: {
    en: "This is the default message sent to guests after they connect. Extracts: hotel name, room number, guest name (PRO only).",
  },
  lbl_tone_ph: {
    en: "e.g., friendly, professional",
  },
  lbl_upload: {
    en: "Upload PDF / TXT",
  },
  lbl_wifi_pass: {
    en: "WiFi Password",
  },
  lbl_wifi_ssid: {
    en: "WiFi SSID",
  },
  label_room: {
    en: "Room",
  },
  loading: {
    en: "Loading tasks...",
  },
  loading_common: {
    en: "Loading...",
  },
  logged_in: {
    en: "Logged In",
  },
  login_button: {
    en: "Sign In",
  },
  login_email: {
    en: "Email",
  },
  login_email_ph: {
    en: "your@email.com",
  },
  login_error: {
    en: "Login failed",
  },
  login_password: {
    en: "Password",
  },
  login_password_ph: {
    en: "Enter your password",
  },
  login_subtitle: {
    en: "Access the admin panel",
  },
  login_title: {
    en: "Sign In",
  },
  login_title_owner: {
    en: "Owner Login",
  },
  staff_access_title: {
    en: "Staff Access",
  },
  staff_access_desc: {
    en: "Welcome to the hotel management dashboard. Manage requests, view tasks, and assist guests efficiently.",
  },
  owner_welcome_title: {
    en: "Welcome back",
  },
  owner_welcome_desc: {
    en: "Access your dashboard to manage conversations, view insights, and configure your AI concierge.",
  },
  login_error_fields: {
    en: "Email and password are required.",
  },
  login_forgot: {
    en: "Forgot password?",
  },
  forgot_email_required: {
    en: "Please enter your email to reset.",
  },
  forgot_email_sent: {
    en: "If the email exists, you'll receive a reset link.",
  },
  forgot_title: {
    en: "Reset Password",
  },
  forgot_send_link: {
    en: "Send reset link",
  },
  logout: {
    en: "Logout",
  },
  yes: {
    en: "Yes",
  },
  no: {
    en: "No",
  },
  time_ago_seconds: {
    en: "{n}s ago",
  },
  time_ago_minutes: {
    en: "{n}m ago",
  },
  time_ago_hours: {
    en: "{n}h ago",
  },
  time_ago_days: {
    en: "{n}d ago",
  },
  mark_done: {
    en: "Mark Done",
  },
  nav_ai_settings: {
    en: "AI Settings",
  },
  nav_conversations: {
    en: "Conversations",
  },
  nav_integrations: {
    en: "Integrations",
  },
  nav_subscription: {
    en: "Subscription",
  },
  nav_help: {
    en: "Help",
  },
  nav_logout: {
    en: "Logout",
  },
  nav_staff_settings: {
    en: "Staff Settings",
  },
  nav_tasks: {
    en: "Tasks",
  },
  new_password: {
    en: "New Password",
  },
  new_password_label: {
    en: "New Password",
  },
  confirm_password_label: {
    en: "Confirm Password",
  },
  reset_title: {
    en: "Reset Password",
  },
  reset_subtitle: {
    en: "Enter and confirm your new password.",
  },
  reset_btn: {
    en: "Save New Password",
  },
  password_mismatch: {
    en: "Passwords do not match",
  },
  reset_success: {
    en: "Password changed! Redirecting...",
  },
  reset_invalid_token: {
    en: "Invalid or expired token.",
  },
  reset_user_not_found: {
    en: "User not found.",
  },
  reset_token_missing: {
    en: "Missing reset token.",
  },
  reset_failed: {
    en: "Reset failed.",
  },
  no_data: {
    en: "No data available",
  },
  password_requirements: {
    en: "Minimum 6 characters",
  },
  pwd_min_length: {
    en: "New password must be at least 6 characters",
  },
  pwd_mismatch: {
    en: "New passwords do not match",
  },
  pwd_change_failed: {
    en: "Failed to change password",
  },
  pwd_change_success: {
    en: "Password changed successfully!",
  },
  network_error: {
    en: "Network error. Please try again.",
  },
  notif_label: {
    en: "Notifications",
  },
  notif_sound_on: {
    en: "Sound on",
  },
  notif_sound_off: {
    en: "Sound off",
  },
  notif_new_tasks: {
    en: "New tasks: {count}",
  },
  notif_new_handoffs: {
    en: "New handoff requests: {count}",
  },
  notif_view_tasks: {
    en: "View tasks",
  },
  notif_view_conversations: {
    en: "View conversations",
  },
  priority_all: {
    en: "All Priorities",
  },
  priority_critical: {
    en: "Critical",
  },
  priority_normal: {
    en: "Normal",
  },
  priority_urgent: {
    en: "Urgent",
  },
  rooms_label: {
    en: "Rooms",
  },
  save_error: {
    en: "Save failed",
  },
  save_success: {
    en: "Saved successfully",
  },
  saving: {
    en: "Saving...",
  },
  sec_abuse: {
    en: "Anti-abuse",
  },
  sec_facts: {
    en: "Hotel Facts",
  },
  sec_welcome: {
    en: "Welcome Message",
  },
  sec_kb: {
    en: "Knowledge Base & Documents",
  },
  sec_persona: {
    en: "Persona & Tone",
  },
  sec_products: {
    en: "Products & Prices",
  },
  select_language: {
    en: "Select language",
  },
  settings_subtitle: {
    en: "Configure bot behavior, persona, and policies.",
  },
  settings_title: {
    en: "AI Assistant & Policies",
  },
  setup_hotel_btn: {
    en: "Add New Hotel",
  },
  owner_hotels_title: {
    en: "Your Hotels",
  },
  owner_hotels_subtitle: {
    en: "Select a hotel to view analytics or add a new hotel.",
  },
  owner_create_title: {
    en: "Create a new hotel + admin",
  },
  owner_platform_settings: {
    en: "Platform Settings",
  },
  owner_hotel_created: {
    en: "Hotel created successfully",
  },
  owner_security_pin_hint: {
    en: "Security PIN (give this to the hotel admin to unlock Integrations):",
  },
  owner_copy_pin: {
    en: "Copy PIN",
  },
  owner_continue_connection: {
    en: "Continue to Connection Center to choose WhatsApp or LINE and test the setup.",
  },
  owner_go_setup: {
    en: "Go to Connection Setup",
  },
  owner_hotel_name: {
    en: "Hotel Name",
  },
  owner_interface_language: {
    en: "Interface Language",
  },
  owner_timezone: {
    en: "Timezone",
  },
  owner_timezone_ph: {
    en: "Europe/Bucharest",
  },
  owner_timezone_hint: {
    en: "Example: Europe/Bucharest",
  },
  owner_admin_name: {
    en: "Admin Name",
  },
  owner_admin_email: {
    en: "Admin Email",
  },
  owner_admin_password: {
    en: "Admin Password",
  },
  owner_lock_language: {
    en: "Lock interface language for Admin UI",
  },
  owner_create_btn: {
    en: "Create Hotel",
  },
  owner_platform_settings_title: {
    en: "Platform Settings",
  },
  owner_secrets_title: {
    en: "Secrets",
  },
  owner_secrets_hint: {
    en: "Values are masked on load. Leave a field empty to keep the current value. Saving a new value overwrites the existing secret.",
  },
  owner_openai_key: {
    en: "OpenAI API Key",
  },
  owner_resend_key: {
    en: "Resend API Key",
  },
  owner_wa_platform_token: {
    en: "WhatsApp Platform Token",
  },
  owner_setup_title: {
    en: "Hotel Setup",
  },
  owner_setup_header: {
    en: "Hotel Connection Setup",
  },
  owner_setup_subtitle: {
    en: "Configure messaging channel",
  },
  owner_channel_title: {
    en: "Communication Channel",
  },
  owner_channel_subtitle: {
    en: "Choose and configure the provider for this hotel.",
  },
  owner_provider: {
    en: "Provider",
  },
  owner_provider_meta_default: {
    en: "WhatsApp (Platform Default)",
  },
  owner_provider_meta_custom: {
    en: "WhatsApp (Custom / BYOC)",
  },
  owner_provider_line: {
    en: "LINE",
  },
  owner_lock_hint: {
    en: "Lock configuration so only you/Admins can change it.",
  },
  owner_lock_messaging: {
    en: "Lock messaging configuration",
  },
  owner_wa_title: {
    en: "WhatsApp Custom Keys",
  },
  owner_wa_phone_id: {
    en: "Phone Number ID",
  },
  owner_wa_phone_id_ph: {
    en: "e.g. 123456789",
  },
  owner_wa_token: {
    en: "Access Token",
  },
  owner_wa_token_ph: {
    en: "Access Token",
  },
  owner_wa_business_id: {
    en: "Business Account ID (optional)",
  },
  owner_wa_business_id_ph: {
    en: "WABA ID",
  },
  owner_wa_hint: {
    en: "Leave blank to keep current values; save empty to revert to platform default.",
  },
  owner_line_title: {
    en: "LINE Channel Keys",
  },
  owner_line_secret: {
    en: "Channel Secret",
  },
  owner_line_secret_ph: {
    en: "Channel Secret",
  },
  owner_line_token: {
    en: "Channel Access Token",
  },
  owner_line_token_ph: {
    en: "Channel Access Token",
  },
  owner_line_webhook: {
    en: "Webhook URL",
  },
  owner_line_webhook_hint: {
    en: "Add this URL in LINE Messaging API settings after saving.",
  },
  owner_copy_webhook: {
    en: "Copy",
  },
  owner_stats_title: {
    en: "Hotel Usage",
  },
  owner_stats_subtitle: {
    en: "Analytics & Performance",
  },
  owner_stats_daily: {
    en: "Daily Usage Metrics",
  },
  owner_stats_date: {
    en: "Date",
  },
  owner_stats_in: {
    en: "Messages IN",
  },
  owner_stats_out: {
    en: "Messages OUT (Bot)",
  },
  owner_stats_tasks_created: {
    en: "Tasks Created",
  },
  owner_stats_tasks_done: {
    en: "Tasks Done",
  },
  owner_stats_llm: {
    en: "LLM Calls",
  },
  owner_no_hotels: {
    en: "No hotels found.",
  },
  owner_btn_setup: {
    en: "Connection Setup",
  },
  owner_btn_usage: {
    en: "View Usage",
  },
  owner_btn_connection_info: {
    en: "Connection Info",
  },
  owner_missing_hotel_id: {
    en: "Missing hotel id",
  },
  owner_created_msg: {
    en: "Hotel {hotel} created. Admin {admin} can now log in at /ui/admin/login.",
  },
  owner_hotel_connection: {
    en: "Hotel connection",
  },
  owner_err_line_keys: {
    en: "LINE requires Channel Secret and Access Token.",
  },
  owner_err_wa_keys: {
    en: "Phone Number ID and Access Token are required for custom WhatsApp.",
  },
  owner_err_save_connection: {
    en: "Failed to save connection.",
  },
  owner_warning: {
    en: "Warning:",
  },
  owner_test_completed: {
    en: "Test completed.",
  },
  owner_err_required: {
    en: "All fields are required.",
  },
  owner_err_create: {
    en: "Failed to create hotel.",
  },
  owner_current_prefix: {
    en: "Current:",
  },
  owner_not_set: {
    en: "Not set",
  },
  owner_checking: {
    en: "Checking...",
  },
  owner_connected: {
    en: "Connected",
  },
  owner_error: {
    en: "Error",
  },
  owner_err_save_platform: {
    en: "Failed to save platform settings.",
  },
  owner_saved: {
    en: "Saved.",
  },
  owner_connection_info_title: {
    en: "Connection Info",
  },
  owner_webhook_url: {
    en: "Webhook URL",
  },
  owner_copy: {
    en: "Copy",
  },
  owner_security_pin_label: {
    en: "Security PIN",
  },
  owner_pin_hint: {
    en: "Give this PIN to the hotel admin to unlock integrations.",
  },
  owner_status_checking: {
    en: "Checking...",
  },
  owner_status_connected: {
    en: "Connected",
  },
  owner_status_error: {
    en: "Error",
  },
  owner_platform_settings_subtitle: {
    en: "Manage platform-level credentials",
  },
  table_id: {
    en: "ID",
  },
  table_name: {
    en: "Name",
  },
  table_action: {
    en: "Action",
  },
  staff_actions: {
    en: "Actions",
  },
  staff_add: {
    en: "Add Staff",
  },
  staff_admin: {
    en: "Staff Admin",
  },
  staff_alert_phone: {
    en: "Alert phone (WhatsApp)",
  },
  staff_alert_phone_hint: {
    en: "WhatsApp number for staff alerts (e.g., reception).",
  },
  staff_alert_phone_ph: {
    en: "wa_id / phone",
  },
  staff_alerts_disabled: {
    en: "Alerts disabled",
  },
  staff_alerts_enabled: {
    en: "Alerts enabled",
  },
  staff_email: {
    en: "Email",
  },
  staff_language_default: {
    en: "Default",
  },
  staff_language_hint: {
    en: "Language in which staff sees task summaries.",
  },
  staff_language_label: {
    en: "Staff language",
  },
  staff_load_failed: {
    en: "Failed to load staff settings",
  },
  staff_name: {
    en: "Name",
  },
  staff_role: {
    en: "Role",
  },
  staff_save_failed: {
    en: "Failed to save",
  },
  staff_saved: {
    en: "Saved",
  },
  staff_subtitle: {
    en: "Manage staff accounts and permissions.",
  },
  staff_title: {
    en: "Staff Settings",
  },
  status_active_custom: {
    en: "Active (custom)",
  },
  status_active_platform: {
    en: "Active (platform managed)",
  },
  status_disconnected: {
    en: "Disconnected",
  },
  status_all: {
    en: "All Statuses",
  },
  status_done: {
    en: "Done",
  },
  status_inprog: {
    en: "In Progress",
  },
  status_open: {
    en: "Open",
  },
  guest_state_pre_stay: {
    en: "Pre-stay",
  },
  guest_state_in_house: {
    en: "In house",
  },
  guest_state_post_stay: {
    en: "Post-stay",
  },
  status_cancelled: {
    en: "Cancelled",
  },
  subtitle_tasks: {
    en: "Manage and track hotel staff requests.",
  },
  success: {
    en: "Success",
  },
  tab_all: {
    en: "All",
  },
  tab_frontdesk: {
    en: "Front Desk",
  },
  tab_housekeeping: {
    en: "Housekeeping",
  },
  tab_maintenance: {
    en: "Maintenance",
  },
  tab_other: {
    en: "Other",
  },
  task_actions: {
    en: "Actions",
  },
  task_created: {
    en: "Created",
  },
  task_id: {
    en: "ID",
  },
  task_priority: {
    en: "Priority",
  },
  task_room: {
    en: "Room",
  },
  task_status: {
    en: "Status",
  },
  task_summary: {
    en: "Summary",
  },
  task_type: {
    en: "Type",
  },
  task_housekeeping: {
    en: "Housekeeping",
  },
  task_maintenance: {
    en: "Maintenance",
  },
  task_frontdesk: {
    en: "Front Desk",
  },
  task_food_beverage: {
    en: "Food & Beverage",
  },
  test_failed: {
    en: "Test failed",
  },
  test_success: {
    en: "Connection successful",
  },
  force_change_title: {
    en: "Set a new password",
  },
  force_change_subtitle: {
    en: "To continue, please set a new password.",
  },
  force_new_password: {
    en: "New Password",
  },
  force_confirm_password: {
    en: "Confirm Password",
  },
  force_save_continue: {
    en: "Save and Continue",
  },
  force_error_mismatch: {
    en: "Password must be at least 6 characters and match.",
  },
  force_error_save: {
    en: "Could not save password.",
  },
  conv_send_to_guest: {
    en: "Send message to guest",
  },
  conv_send_message_ph: {
    en: "Write the message...",
  },
  btn_send: {
    en: "Send",
  },
  ai_kb_hint: {
    en: "Upload rules/menus/guides; extracted text will be used in answers.",
  },
  ai_additional_notes_ph: {
    en: "Additional notes, if needed.",
  },
  ai_products_title: {
    en: "Products & Prices (Menu / Services)",
  },
  ai_products_upload_hint: {
    en: "Upload restaurant/bar/services menu; extracted text will be added to the list.",
  },
  ai_products_info_hint: {
    en: "Provide the official list of products/services and prices the bot can use. If a product is missing, the bot will say it has no information.",
  },
  ai_upload_select_file: {
    en: "Select a file",
  },
  ai_upload_processed: {
    en: "File processed",
  },
  ai_upload_failed: {
    en: "Upload failed",
  },
  ai_menu_upload_success: {
    en: "Menu uploaded successfully",
  },
  th_guest: {
    en: "Guest",
  },
  th_guest_state: {
    en: "Guest State",
  },
  th_hotel: {
    en: "Hotel",
  },
  th_id: {
    en: "ID",
  },
  th_last_message: {
    en: "Last Message",
  },
  th_open_tasks: {
    en: "Open Tasks",
  },
  th_room: {
    en: "Room",
  },
  th_stay: {
    en: "Stay",
  },
  th_updated: {
    en: "Updated",
  },
  th_actions: {
    en: "Actions",
  },
  gdpr_export: {
    en: "Export Guest Data",
  },
  gdpr_delete: {
    en: "Delete Guest Data",
  },
  gdpr_export_error: {
    en: "Export failed",
  },
  gdpr_delete_confirm: {
    en: "Are you sure you want to permanently anonymize this guest's data? This cannot be undone.",
  },
  gdpr_delete_success: {
    en: "Guest data anonymized.",
  },
  gdpr_delete_error: {
    en: "Deletion failed",
  },
  title_tasks: {
    en: "Tasks Overview",
  },
  usage: {
    en: "Usage",
  },
  warning: {
    en: "Warning",
  },
  whatsapp_business_id: {
    en: "Business Account ID",
  },
  whatsapp_business_id_ph: {
    en: "Business Account ID",
  },
  whatsapp_connected: {
    en: "Connected",
  },
  whatsapp_disconnected: {
    en: "Disconnected",
  },
  whatsapp_phone_id: {
    en: "Phone Number ID",
  },
  whatsapp_phone_id_ph: {
    en: "Phone Number ID",
  },
  whatsapp_section: {
    en: "WhatsApp Configuration",
  },
  whatsapp_status: {
    en: "Status",
  },
  whatsapp_token: {
    en: "Access Token",
  },
  whatsapp_token_ph: {
    en: "Paste access token",
  },
  whatsapp_webhook_hint: {
    en: "Webhook URL: /webhook/whatsapp (configure in Meta)",
  },
  // Service toggles section
  sec_services: {
    en: "Available Services",
  },
  lbl_allow_housekeeping: {
    en: "Housekeeping Requests",
  },
  housekeeping_hint: {
    en: "Cleaning, towels, toiletries, laundry",
  },
  lbl_hk_room_cleaning: {
    en: "Room Cleaning",
  },
  lbl_hk_towels_toiletries: {
    en: "Towels & Toiletries",
  },
  hk_towels_hint: {
    en: "Soap, shampoo, toilet paper",
  },
  lbl_hk_bed_linen: {
    en: "Bed Linen",
  },
  lbl_hk_laundry: {
    en: "Laundry Service",
  },
  lbl_hk_extra_amenities: {
    en: "Extra Amenities",
  },
  hk_amenities_hint: {
    en: "Pillows, blankets, iron, slippers",
  },
  lbl_allow_food_beverage: {
    en: "Food & Beverage Orders",
  },
  food_beverage_hint: {
    en: "Room service, drinks, menu items",
  },
  services_safety_note: {
    en: "Maintenance and emergency requests are always enabled for safety.",
  },
  // Session Security (Basic Tier)
  sec_session_security: {
    en: "Session Security (Basic Tier)",
  },
  lbl_qr_session_expiry: {
    en: "Enable QR Session Expiry",
  },
  qr_session_hint: {
    en: "Guests must re-scan QR code after session expires. Prevents abuse from guests who left.",
  },
  qr_session_warning: {
    en: "⚠️ If disabled: Previous guests can continue chatting indefinitely after checkout, potentially accessing hotel services or information meant for current guests.",
  },
  lbl_session_hours: {
    en: "Session Validity",
  },
  session_hours_hint: {
    en: "How long the session stays active after QR scan.",
  },
  qr_hours_24: {
    en: "24 hours",
  },
  qr_hours_48_recommended: {
    en: "48 hours (Recommended)",
  },
  session_pro_note: {
    en: "PRO tier hotels use PMS checkout dates instead - session expiry is automatic.",
  },
  // ==================== HELP CENTER ====================
  help_title: {
    en: "Help Center",
  },
  help_subtitle: {
    en: "Setup guides, configuration tips, and troubleshooting.",
  },
  help_tab_quickstart: {
    en: "Quick Start",
  },
  help_tab_connections: {
    en: "Connection Guides",
  },
  help_tab_features: {
    en: "Features",
  },
  help_tab_faq: {
    en: "FAQ",
  },
  help_quickstart_intro_title: {
    en: "Get your hotel bot running in 4 steps!",
  },
  help_quickstart_intro_text: {
    en: "Follow this guide to configure and activate your AI assistant.",
  },
  help_step1_title: {
    en: "Configure AI Settings",
  },
  help_step1_desc: {
    en: "Set your hotel name, welcome tone, WiFi credentials, breakfast hours, and other policies that the bot will use when answering guests.",
  },
  help_step2_title: {
    en: "Connect Messaging Channel",
  },
  help_step2_desc: {
    en: "Connect your LINE (Thailand) or WhatsApp (Europe) account. You'll need API credentials from LINE Developers or Meta for Business.",
  },
  help_step3_title: {
    en: "Print QR Codes",
  },
  help_step3_desc: {
    en: "Generate and print QR codes for each room. Place them in visible locations (desk, nightstand, bathroom). Guests scan to connect instantly.",
  },
  help_step4_title: {
    en: "Test the Bot!",
  },
  help_step4_desc: {
    en: "Use your phone to scan a room QR code or send a test message. Verify the bot responds correctly with your hotel information.",
  },
  help_step4_example: {
    en: "Example: Send \"Connect Room 101\" or scan QR code, then ask \"What's the WiFi password?\"",
  },
  help_restart_tour_text: {
    en: "Want to see the guided tour again?",
  },
  help_restart_tour_btn: {
    en: "Restart Tour",
  },
  help_go_to_ai_settings: {
    en: "Go to AI Settings",
  },
  help_go_to_integrations: {
    en: "Go to Integrations",
  },
  help_view_guide: {
    en: "View Guide",
  },
  help_download_qr: {
    en: "Download QR Codes",
  },
  help_recommended_th: {
    en: "Recommended for Thailand",
  },
  help_recommended_eu: {
    en: "Recommended for Europe",
  },
  help_line_desc: {
    en: "Connect LINE Official Account for Thai market hotels.",
  },
  help_whatsapp_desc: {
    en: "Connect WhatsApp Business for European market hotels.",
  },
  help_common_errors: {
    en: "Common Errors",
  },
  help_error: {
    en: "Error",
  },
  help_solution: {
    en: "Solution",
  },
  help_feature_toggles: {
    en: "Service Toggles",
  },
  help_feature_toggles_desc: {
    en: "Control which services the bot can handle:",
  },
  help_toggle_hk: {
    en: "Cleaning, towels, laundry requests",
  },
  help_toggle_fb: {
    en: "Room service, menu orders",
  },
  help_toggle_tip: {
    en: "Disable services your hotel doesn't offer to avoid guest confusion.",
  },
  help_feature_menu: {
    en: "Menu Upload",
  },
  help_feature_menu_desc: {
    en: "Upload your restaurant/bar menu so the bot can answer food questions:",
  },
  help_menu_format: {
    en: "Supported formats: PDF, TXT",
  },
  help_menu_prices: {
    en: "Include prices for accurate responses",
  },
  help_menu_update: {
    en: "Update anytime from AI Settings",
  },
  help_upload_menu: {
    en: "Upload Menu",
  },
  help_feature_session: {
    en: "Session Security",
  },
  help_feature_session_desc: {
    en: "Prevent abuse from guests who already checked out:",
  },
  help_session_expiry: {
    en: "Sessions expire after 24-48 hours",
  },
  help_session_rescan: {
    en: "Guests must re-scan QR to continue",
  },
  help_session_pro: {
    en: "PRO tier uses PMS checkout dates automatically",
  },
  help_feature_kb: {
    en: "Knowledge Base",
  },
  help_feature_kb_desc: {
    en: "Upload documents for the bot to learn from:",
  },
  help_kb_rules: {
    en: "Hotel rules and policies",
  },
  help_kb_attractions: {
    en: "Local attractions guide",
  },
  help_kb_services: {
    en: "Service descriptions",
  },
  help_upload_docs: {
    en: "Upload Documents",
  },
  help_faq1_q: {
    en: "The bot doesn't respond to messages",
  },
  help_faq1_a: {
    en: "Check the following:",
  },
  help_faq1_a1: {
    en: "Verify webhook URL is correctly configured in LINE/Meta",
  },
  help_faq1_a2: {
    en: "Check that tokens haven't expired",
  },
  help_faq1_a3: {
    en: "For LINE: Ensure \"Use webhook\" is enabled",
  },
  help_faq1_a4: {
    en: "For WhatsApp: Verify webhook subscriptions (messages, message_status)",
  },
  help_check_connection: {
    en: "Check Connection",
  },
  help_faq2_q: {
    en: "Bot responds in wrong language",
  },
  help_faq2_a: {
    en: "The bot auto-detects guest language. If it's responding incorrectly:",
  },
  help_faq2_a1: {
    en: "Check \"Staff Language\" setting in your hotel profile",
  },
  help_faq2_a2: {
    en: "Verify welcome message language matches your market",
  },
  help_faq2_a3: {
    en: "For bilingual hotels, enable \"Also send in English\" option",
  },
  help_faq3_q: {
    en: "Guests can't order food",
  },
  help_faq3_a: {
    en: "Check the following:",
  },
  help_faq3_a1: {
    en: "Verify \"Food & Beverage\" toggle is enabled in AI Settings",
  },
  help_faq3_a2: {
    en: "Upload your menu with prices",
  },
  help_faq3_a3: {
    en: "If product isn't in menu, bot will say it doesn't have info",
  },
  help_faq4_q: {
    en: "QR code doesn't work",
  },
  help_faq4_a: {
    en: "Common QR issues:",
  },
  help_faq4_a1: {
    en: "LINE: Guest must first add the bot as friend",
  },
  help_faq4_a2: {
    en: "WhatsApp: Opens wa.me link - needs WhatsApp installed",
  },
  help_faq4_a3: {
    en: "Re-download QR codes after changing messaging provider",
  },
  help_faq5_q: {
    en: "Session expired message",
  },
  help_faq5_a: {
    en: "If guests see \"session expired\":",
  },
  help_faq5_a1: {
    en: "This is a security feature (QR Session Expiry)",
  },
  help_faq5_a2: {
    en: "Guest must re-scan room QR to reconnect",
  },
  help_faq5_a3: {
    en: "Adjust session hours (24h/48h) in AI Settings",
  },
  help_faq5_a4: {
    en: "PRO tier: Uses PMS checkout date instead",
  },
  help_faq6_q: {
    en: "How to transfer to human staff?",
  },
  help_faq6_a: {
    en: "When the bot can't help, guests can:",
  },
  help_faq6_a1: {
    en: "Say \"talk to human\" or \"speak to staff\"",
  },
  help_faq6_a2: {
    en: "A task will be created for your staff",
  },
  help_faq6_a3: {
    en: "Staff can reply directly from the Tasks page",
  },
  // ==================== LINE CONNECTION GUIDE ====================
  help_line_step1_title: {
    en: "Create LINE Messaging API Channel",
  },
  help_line_step1_1: {
    en: "Go to LINE Developers Console",
  },
  help_line_step1_2: {
    en: "Create a new Provider (or use existing)",
  },
  help_line_step1_3: {
    en: "Create a new Messaging API channel",
  },
  help_line_step1_4: {
    en: "Link to your LINE Official Account",
  },
  help_line_step1_tip: {
    en: "You can create a free LINE Official Account at manager.line.biz",
  },
  help_line_step2_title: {
    en: "Get Your Credentials",
  },
  help_line_step2_1: {
    en: "Open your Messaging API channel",
  },
  help_line_step2_2: {
    en: "Go to Basic settings tab, copy Channel Secret",
  },
  help_line_step2_3: {
    en: "Go to Messaging API tab",
  },
  help_line_step2_4: {
    en: "Under Channel access token section, click Issue",
  },
  help_line_token_warning_title: {
    en: "⚠️ Do NOT use short-lived tokens!",
  },
  help_line_token_warning_text: {
    en: "In LINE Developers Console → Messaging API tab → Channel access token: Click \"Issue\". Ensure you generate a LONG-LIVED token that does not expire. Do not use the 24-hour token, or your bot will stop working tomorrow!",
  },
  help_line_step2_tip: {
    en: "After issuing the token, copy it immediately. You won't be able to see it again!",
  },
  help_line_step3_title: {
    en: "Configure in AI Hotel Suite",
  },
  help_line_step3_1: {
    en: "Go to Integrations page",
  },
  help_line_step3_2: {
    en: "Click Configure on Messaging Provider",
  },
  help_line_step3_3: {
    en: "Select LINE from dropdown",
  },
  help_line_step3_4: {
    en: "Paste your Channel Secret and Access Token",
  },
  help_line_step3_5: {
    en: "Click Test Connection",
  },
  help_line_step3_6: {
    en: "Copy the Webhook URL that appears",
  },
  help_line_step4_title: {
    en: "Configure Webhook in LINE",
  },
  help_line_step4_1: {
    en: "Go back to LINE Developers Console",
  },
  help_line_step4_2: {
    en: "Open Messaging API tab > Webhook settings",
  },
  help_line_step4_3: {
    en: "Paste the Webhook URL from AI Hotel Suite",
  },
  help_line_step4_4: {
    en: "Enable Use webhook",
  },
  help_line_step4_5: {
    en: "Click Verify to test",
  },
  help_line_step4_warning: {
    en: "Important: Disable auto-reply in LINE Official Account Manager to avoid duplicate messages.",
  },
  help_line_err1_sol: {
    en: "Re-issue token in LINE Developers Console",
  },
  help_line_err2_sol: {
    en: "Check firewall, ensure HTTPS is configured",
  },
  help_line_err3: {
    en: "No messages received",
  },
  help_line_err3_sol: {
    en: "Enable \"Use webhook\" in LINE settings",
  },
  help_line_err4: {
    en: "Bot not responding",
  },
  help_line_err4_sol: {
    en: "Disable auto-reply in LINE Manager",
  },
  // ==================== WHATSAPP CONNECTION GUIDE ====================
  help_wa_step1_title: {
    en: "Set Up Meta Business Account",
  },
  help_wa_step1_1: {
    en: "Go to Meta Business Suite",
  },
  help_wa_step1_2: {
    en: "Create or use existing Business Account",
  },
  help_wa_step1_3: {
    en: "Complete business verification (may take 1-3 days)",
  },
  help_wa_step1_tip: {
    en: "Business verification requires official documents. Start this early!",
  },
  help_wa_step2_title: {
    en: "Create WhatsApp App",
  },
  help_wa_step2_1: {
    en: "Go to Meta Developers",
  },
  help_wa_step2_2: {
    en: "Create a new App > Select Business type",
  },
  help_wa_step2_3: {
    en: "Add WhatsApp product to your app",
  },
  help_wa_step2_4: {
    en: "Note your Phone Number ID and WABA ID",
  },
  help_wa_step3_title: {
    en: "Generate Access Token",
  },
  help_wa_step3_1: {
    en: "Go to Business Settings > System Users",
  },
  help_wa_step3_2: {
    en: "Create a System User with Admin role",
  },
  help_wa_step3_3: {
    en: "Assign WhatsApp assets to this user",
  },
  help_wa_step3_4: {
    en: "Generate token with whatsapp_business_messaging permission",
  },
  help_wa_step3_warning: {
    en: "Use a permanent token (System User), not the temporary test token!",
  },
  help_wa_step4_title: {
    en: "Configure in AI Hotel Suite",
  },
  help_wa_step4_1: {
    en: "Go to Integrations page",
  },
  help_wa_step4_2: {
    en: "Click Configure on Messaging Provider",
  },
  help_wa_step4_3: {
    en: "Select WhatsApp (Custom)",
  },
  help_wa_step4_4: {
    en: "Enter Phone Number ID, Access Token, WABA ID",
  },
  help_wa_step4_5: {
    en: "Click Test Connection",
  },
  help_wa_step4_6: {
    en: "Copy Webhook URL and Verify Token",
  },
  help_wa_step5_title: {
    en: "Configure Webhook in Meta",
  },
  help_wa_step5_1: {
    en: "Go to Meta Developers > WhatsApp > Configuration",
  },
  help_wa_step5_2: {
    en: "Click Edit next to Webhook",
  },
  help_wa_step5_3: {
    en: "Paste the Callback URL (Webhook URL from AI Hotel Suite)",
  },
  help_wa_step5_4: {
    en: "Paste the Verify Token",
  },
  help_wa_step5_5: {
    en: "Click Verify and save",
  },
  help_wa_step5_6: {
    en: "Subscribe to: messages, message_status",
  },
  help_wa_err1_sol: {
    en: "Generate new token in Meta Developers",
  },
  help_wa_err2_sol: {
    en: "Copy exact ID from WhatsApp > Getting Started",
  },
  help_wa_err3_sol: {
    en: "Ensure token has whatsapp_business_messaging permission",
  },
  help_wa_err4: {
    en: "Messages not delivered",
  },
  help_wa_err4_sol: {
    en: "First message to user must be template-based",
  },
  // Onboarding Tour Translations
  onb_next: {
    en: "Next",
  },
  onb_prev: {
    en: "Previous",
  },
  onb_done: {
    en: "Done",
  },
  onb_welcome_title: {
    en: "Welcome to AI Hotel Suite!",
  },
  onb_welcome_desc: {
    en: "Let's configure your AI Concierge step by step. This tour will guide you through all the features.",
  },
  onb_ai_settings_title: {
    en: "AI Settings",
  },
  onb_ai_settings_desc: {
    en: "This is your bot's brain. Configure personality, knowledge, and services here.",
  },
  onb_welcome_msg_title: {
    en: "Welcome Message & Tone",
  },
  onb_welcome_msg_desc: {
    en: "Choose your bot's tone (Friendly or Professional) and preview what guests will see.",
  },
  onb_facts_title: {
    en: "Hotel Facts",
  },
  onb_facts_desc: {
    en: "Enter WiFi password, breakfast hours, check-in/out times. The bot will answer these automatically.",
  },
  onb_kb_title: {
    en: "Knowledge Base",
  },
  onb_kb_desc: {
    en: "Upload your menu, rules, or guides as PDF/TXT. The bot learns from these documents.",
  },
  onb_services_title: {
    en: "Available Services",
  },
  onb_services_desc: {
    en: "Enable/disable Housekeeping requests, Food & Beverage orders, and other services.",
  },
  onb_security_title: {
    en: "Session Security",
  },
  onb_security_desc: {
    en: "Set QR session expiry for guest access control. Protects guest privacy.",
  },
  onb_save_title: {
    en: "Save Button",
  },
  onb_save_desc: {
    en: "Don't forget to save your changes! A notification will appear when saved.",
  },
  onb_integrations_title: {
    en: "Integrations",
  },
  onb_integrations_desc: {
    en: "Connect WhatsApp or LINE here. Thai hotels: use LINE. Others: use WhatsApp.",
  },
  onb_conversations_title: {
    en: "Conversations",
  },
  onb_conversations_desc: {
    en: "View all guest chats in real-time. Click any conversation to see details.",
  },
  onb_tasks_title: {
    en: "Tasks",
  },
  onb_tasks_desc: {
    en: "Guest requests appear here automatically. Filter by department or priority.",
  },
  onb_notifications_title: {
    en: "Notifications",
  },
  onb_notifications_desc: {
    en: "Real-time alerts for new messages and tasks. Click to see details.",
  },
  onb_profile_title: {
    en: "Profile & Security",
  },
  onb_profile_desc: {
    en: "Change your password and logout from here. Keep your account secure!",
  },
  onb_finish_title: {
    en: "You're All Set!",
  },
  onb_finish_desc: {
    en: "Start by filling in AI Settings, then connect your messaging platform. Good luck!",
  },
  onb_pms_title: {
    en: "PMS Configuration",
  },
  onb_pms_desc: {

    en: "Connect your Property Management System (Apaleo & Cloudbeds) for automatic guest data.",
  },
  onb_messaging_title: {
    en: "Messaging Provider",
  },
  onb_messaging_desc: {
    en: "Configure WhatsApp or LINE credentials. Thai hotels should use LINE for best results.",
  },
  onb_roomqr_title: {
    en: "Room QR Generator",
  },
  onb_roomqr_desc: {
    en: "Generate QR codes for each room. Guests scan to start a conversation with pre-filled room number.",
  },
  onb_search_title: {
    en: "Search Conversations",
  },
  onb_search_desc: {
    en: "Find conversations by guest name, phone, or room number.",
  },
  onb_chatlist_title: {
    en: "Conversation List",
  },
  onb_chatlist_desc: {
    en: "Click any row to see full conversation history and respond manually if needed.",
  },
  onb_takecontrol_title: {
    en: "Take Control",
  },
  onb_takecontrol_desc: {
    en: "Pause the AI and respond manually. Use this for complex issues or VIP guests!",
  },
  onb_manualreply_title: {
    en: "Manual Reply",
  },
  onb_manualreply_desc: {
    en: "Type your message here when AI is paused. Click Return to AI when done.",
  },
  onb_critical_title: {
    en: "Critical Alerts",
  },
  onb_critical_desc: {
    en: "Urgent requests that need immediate attention appear here in red.",
  },
  onb_filters_title: {
    en: "Filters",
  },
  onb_filters_desc: {
    en: "Filter tasks by department (Housekeeping, Maintenance, Front Desk) or priority.",
  },
};
const I18N = {
  t: (key, lang) => {
    const l = lang || localStorage.getItem('app_lang') || 'en';
    const entry = translations[key];
    if (!entry) {
      console.warn(`[i18n] Missing translation key: ${key}`);
      return key;
    }
    return entry[l] || entry.en || key;
  },
  apply() {
    const path = window.location.pathname || "";
    const lang = path.startsWith("/ui/owner")
      ? "en"
      : (localStorage.getItem('app_lang') || 'en');
    // Translate text content
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      el.innerText = I18N.t(key, lang);
    });
    // Translate placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.setAttribute('placeholder', I18N.t(key, lang));
    });
    // Translate title attributes
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      el.setAttribute('title', I18N.t(key, lang));
    });
  },
  setLang(lang) {
    localStorage.setItem('app_lang', lang || 'en');
    I18N.apply();
  },
  initSelect(selectId) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const lang = localStorage.getItem('app_lang') || 'en';
    sel.value = lang;
    sel.addEventListener('change', (e) => {
      I18N.setLang(e.target.value);
      // Trigger custom event for pages that need to reload data
      window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: e.target.value } }));
    });
  },
  getCurrentLang() {
    return localStorage.getItem('app_lang') || 'en';
  },
  async loadAdminConfig() {
    const token = localStorage.getItem("token");
    if (!token) return null;
    try {
      const resp = await fetch("/admin/ui-config", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (err) {
      console.warn("Failed to load admin ui-config", err);
      return null;
    }
  },
  applyLockState(config) {
    if (!config) return;
    const path = window.location.pathname || "";
    if (path.startsWith("/ui/admin/login")) return;
    const { interface_language, language_locked } = config;
    if (interface_language) {
      I18N.setLang(interface_language);
      document.querySelectorAll("#lang-select").forEach(sel => {
        sel.value = interface_language;
      });
    }
    if (language_locked) {
      document.querySelectorAll("#lang-select").forEach(sel => {
        sel.disabled = true;
        sel.title = "Language locked by owner";
      });
    }
  }
};
// Auto-initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  if (!localStorage.getItem('app_lang')) {
    localStorage.setItem('app_lang', 'en');
  }
  I18N.apply();
  // For admin UI: load per-hotel language config and lock if needed.
  // Do NOT apply language lock on the admin login page (it must remain user-selectable).
  const path = window.location.pathname || "";
  const isAdminLogin = path.startsWith("/ui/admin/login");
  const isOwnerPage = path.startsWith("/ui/owner");
  if (!isAdminLogin && !isOwnerPage) {
    I18N.loadAdminConfig().then(cfg => {
      if (cfg) {
        I18N.applyLockState(cfg);
      }
    });
  }
});
