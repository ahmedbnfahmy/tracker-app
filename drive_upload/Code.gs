/**
 * Tracker — upload screenshots, then expose an "anyone with the link" Drive URL.
 *
 * Setup (once — folder owner only):
 * 1. https://script.google.com → New project
 * 2. Paste this file into Code.gs
 * 3. Set FOLDER_ID to your Drive folder ID
 * 4. Deploy → New deployment → Web app
 *      Execute as: Me
 *      Who has access: Anyone
 * 5. In Tracker → Share session → paste the .../exec URL
 *
 * The script uploads files and makes the folder viewable by anyone with the link.
 * Tracker then shows that Drive folder link so you can share it.
 */

var FOLDER_ID = "PASTE_YOUR_FOLDER_ID_HERE";

function ensureAnyoneWithLink_(folder) {
  // Anyone with the link can VIEW the folder (and files inside once shared)
  folder.setSharing(
    DriveApp.Access.ANYONE_WITH_LINK,
    DriveApp.Permission.VIEW
  );
  return folder.getUrl();
}

function doPost(e) {
  try {
    if (!FOLDER_ID || FOLDER_ID === "PASTE_YOUR_FOLDER_ID_HERE") {
      return json_({ error: "Set FOLDER_ID in Apps Script first" });
    }
    if (!e || !e.postData || !e.postData.contents) {
      return json_({ error: "Empty body" });
    }

    var data = JSON.parse(e.postData.contents);
    var filename = data.filename || ("capture_" + Date.now() + ".png");
    var mimeType = data.mimeType || "image/png";
    var content = data.content;
    if (!content) {
      return json_({ error: "Missing content" });
    }

    var folder = DriveApp.getFolderById(FOLDER_ID);
    var folderUrl = ensureAnyoneWithLink_(folder);

    var blob = Utilities.newBlob(
      Utilities.base64Decode(content),
      mimeType,
      filename
    );
    var file = folder.createFile(blob);
    file.setSharing(
      DriveApp.Access.ANYONE_WITH_LINK,
      DriveApp.Permission.VIEW
    );

    return json_({
      id: file.getId(),
      name: file.getName(),
      fileUrl: file.getUrl(),
      folderUrl: folderUrl,
      shareLink: folderUrl,
    });
  } catch (err) {
    return json_({ error: String(err) });
  }
}

function doGet() {
  try {
    if (!FOLDER_ID || FOLDER_ID === "PASTE_YOUR_FOLDER_ID_HERE") {
      return json_({ error: "Set FOLDER_ID in Apps Script first" });
    }
    var folder = DriveApp.getFolderById(FOLDER_ID);
    var folderUrl = ensureAnyoneWithLink_(folder);
    return json_({
      ok: true,
      folderUrl: folderUrl,
      shareLink: folderUrl,
    });
  } catch (err) {
    return json_({ error: String(err) });
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
