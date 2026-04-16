function checkAvailableModels() {
    const apiKey = "AIzaSyBnmyJ1ZRLRYxAuV7CHBRu9u3CAzwXGzeY"; // あなたのキー
    const url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + apiKey;
    const response = UrlFetchApp.fetch(url);
    Logger.log(response.getContentText());
}

function generateDailyNewsScript() {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName("Main_Scripts");

    const now = new Date();
    const todayStr = Utilities.formatDate(now, "JST", "yyyy/MM/dd");
    const dayLabels = ["日", "月", "火", "水", "木", "金", "土"];
    const todayLabel = dayLabels[now.getDay()];

    let data = sheet.getDataRange().getValues();
    let targetRow = -1;
    for (let i = 0; i < data.length; i++) {
        if (data[i][0] instanceof Date) {
            const rowDate = Utilities.formatDate(data[i][0], "JST", "yyyy/MM/dd");
            if (rowDate === todayStr) {
                targetRow = i + 1;
                break;
            }
        }
    }

    if (targetRow === -1) {
        targetRow = sheet.getLastRow() + 1;
        sheet.getRange(targetRow, 1).setValue(todayStr);
        sheet.getRange(targetRow, 2).setValue(todayLabel);
    }

    const apiKey = GEMINI_API_KEY;
    const apiEndpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + apiKey;

    // 【修正】プロンプトを詳細化し、確実にデータを出させます
    const payload = {
        "contents": [{
            "parts": [{
                "text": "最新のAIニュースを1つ選び、以下のJSON形式で出力してください。解説は不要です。\n\n" +
                    "{\n" +
                    "  \"ai_model\": \"Gemini 2.5 Flash\",\n" +
                    "  \"script_full\": \"ニュースの詳細を解説する、動画用の2分程度の丁寧な読み上げ台本\",\n" +
                    "  \"summary_sentence\": \"画面上部に表示する、このニュースの核心を突く1文\",\n" +
                    "  \"headline_short\": \"画面左側に表示する、5〜10文字程度の短いタイトル\",\n" +
                    "  \"image_keyword\": \"このニュースの内容を象徴する、画像検索に最適な英語のキーワード1つ\"\n" +
                    "}"
            }]
        }]
    };

    const options = {
        "method": "post",
        "contentType": "application/json",
        "payload": JSON.stringify(payload)
    };

    try {
        const response = UrlFetchApp.fetch(apiEndpoint, options);
        const result = JSON.parse(response.getContentText());

        let rawText = result.candidates[0].content.parts[0].text;

        // JSONの前後にある余計な文字（Markdownの枠など）を除去
        const jsonMatch = rawText.match(/\{[\s\S]*\}/);
        if (!jsonMatch) throw new Error("JSONが見つかりませんでした。");

        const newsData = JSON.parse(jsonMatch[0]);

        // 書き込み（C列〜G列）
        sheet.getRange(targetRow, 3).setValue(newsData.ai_model);         // C列
        sheet.getRange(targetRow, 4).setValue(newsData.script_full);      // D列
        sheet.getRange(targetRow, 5).setValue(newsData.summary_sentence); // E列
        sheet.getRange(targetRow, 6).setValue(newsData.headline_short);   // F列
        sheet.getRange(targetRow, 7).setValue(newsData.image_keyword);    // G列

        SpreadsheetApp.flush(); // 即時反映
        Logger.log("正常に書き込みました: " + todayStr);

    } catch (e) {
        Logger.log("エラー発生: " + e.toString());
    }
}