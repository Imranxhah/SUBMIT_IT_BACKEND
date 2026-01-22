# App Version & Force Update Guide

This system allows you to manage the minimum required application version and force users to update their app if it is outdated.

## 1. API Endpoint Details

**Endpoint:** `GET /api/app-version/`  
**Access:** Public (No authentication required)

### Response Structure
The endpoint returns the **latest** version entry created in the database.

```json
{
  "version": "1.0.2",
  "force_update": true,
  "message": "A critical security update is available. Please update immediately.",
  "store_url": "https://play.google.com/store/apps/details?id=com.yourapp"
}
```

### Field Definitions

| Field | Type | Description |
| :--- | :--- | :--- |
| `version` | String | The version string (e.g., "1.0.0", "2.1.5"). |
| `force_update` | Boolean | `true` if this version is mandatory. `false` if it is optional. |
| `message` | String | A custom message to display to the user in the update dialog. |
| `store_url` | String | (Optional) Direct link to the App Store or Play Store. |

---

## 2. Managing Versions (Admin Panel)

1.  Log in to the Django Admin panel (usually at `/admin/`).
2.  Scroll to the **Core** section.
3.  Click on **App versions**.
4.  Click **Add app version**.
5.  Fill in the details:
    *   **Version:** The new version number.
    *   **Force update:** Check this box if users on older versions *must* update.
    *   **Message:** "New features added!" or "Critical bug fix."
    *   **Store url:** Link to your app.
6.  Click **Save**.

**Note:** The API always returns the entry with the *latest* creation timestamp.

---

## 3. Frontend Implementation Logic (Example)

When your mobile or web app starts, it should call this endpoint and compare the response with its current running version.

**Pseudo-code Example:**

```javascript
async function checkAppVersion() {
  const currentVersion = "1.0.0"; // The app's installed version
  
  try {
    const response = await fetch('https://your-domain.com/api/app-version/');
    const data = await response.json();
    
    // Compare versions (using a semantic version comparison library is recommended)
    if (data.version !== currentVersion) {
      if (data.force_update) {
        // BLOCK user interaction
        showModal({
          title: "Update Required",
          body: data.message,
          buttonText: "Update Now",
          onPress: () => openUrl(data.store_url),
          dismissible: false
        });
      } else {
        // OPTIONAL update
        showModal({
          title: "Update Available",
          body: data.message,
          buttonText: "Update",
          cancelText: "Later",
          onPress: () => openUrl(data.store_url),
          dismissible: true
        });
      }
    }
  } catch (error) {
    console.error("Failed to check version", error);
    // Optionally allow the user to proceed if the check fails
  }
}
```
