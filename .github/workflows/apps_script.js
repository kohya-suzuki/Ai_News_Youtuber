/**
 * Main_Scriptsの2行目に最新ニュースを挿入する
 */
function generateDailyNewsScript() {
    const props = PropertiesService.getScriptProperties();
    const apiKey = props.getProperty('GEMINI_API_KEY');
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName("Main_Scripts");

    if (!sheet) {
        Logger.log("エラー: 'Main_Scripts' という名前のシートが見つかりません。");
        return;
    }

    // 今日の日時
    const now = new Date();
    const todayStr = Utilities.formatDate(now, "JST", "yyyy/MM/dd HH:mm");
    const dayLabels = ["日", "月", "火", "水", "木", "金", "土"];
    const todayLabel = dayLabels[now.getDay()];

    Logger.log("処理開始: " + todayStr);

    // 1. タイトル行の直後（2行目）に空行を挿入
    sheet.insertRowBefore(2);
    const targetRow = 2;
    Logger.log("2行目に行を挿入しました。");

    // 2. Gemini API へのリクエスト準備
    const apiEndpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + apiKey;

    const payload = {
        "contents": [{
            "parts": [{
                "text": "優先して2026年における今月の最新のAI関連ニュースを1つ選び、以下のJSON形式のみで出力してください。余計な説明文は不要です。\n\n" +
                    "{\n" +
                    "  \"ai_model\": \"Gemini 2.5 Flash\",\n" +
                    "  \"title\": \"ニュースのタイトル\",\n" +
                    "  \"url\": \"ニュースの参照URL\",\n" +
                    "  \"script_full\": \"2分程度の動画用読み上げ台本\",\n" +
                    "  \"summary_sentence\": \"要約1文\",\n" +
                    "  \"headline_short\": \"短い見出し(10文字以内)\",\n" +
                    "  \"image_keyword\": \"英語の画像検索キーワード\",\n" +
                    "  \"complaint\": \"AIが考える人間に対しての愚痴(溜め息などは不要)\"\n" +
                    "}"
            }]
        }]
    };

    const options = {
        "method": "post",
        "contentType": "application/json",
        "payload": JSON.stringify(payload),
        "muteHttpExceptions": true
    };

    try {
        Logger.log("APIリクエスト送信中...");
        const response = UrlFetchApp.fetch(apiEndpoint, options);
        const responseCode = response.getResponseCode();
        const responseText = response.getContentText();

        if (responseCode !== 200) {
            Logger.log("APIエラー (Code: " + responseCode + "): " + responseText);
            sheet.deleteRow(targetRow); // 失敗したら挿入した行を消す
            return;
        }

        const result = JSON.parse(responseText);
        let rawText = result.candidates[0].content.parts[0].text;

        // JSON部分のみを抽出
        const jsonMatch = rawText.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            Logger.log("JSON抽出失敗。生の回答: " + rawText);
            return;
        }

        const newsData = JSON.parse(jsonMatch[0]);
        Logger.log("データ取得成功: " + newsData.title);

        // 3. スプレッドシートへの書き込み
        // 列順: A:日時, B:曜日, C:モデル, D:台本, E:要約, F:見出し, G:画像KW, H:YouTube(空), I:タイトル, J:元URL, K:愚痴
        const rowValues = [[
            todayStr,           // A
            todayLabel,         // B
            newsData.ai_model,  // C
            newsData.script_full, // D
            newsData.summary_sentence, // E
            newsData.headline_short, // F
            newsData.image_keyword, // G
            "",                 // H (空)
            newsData.title,     // I
            newsData.url,       // J
            newsData.complaint  // K
        ]];

        sheet.getRange(targetRow, 1, 1, 11).setValues(rowValues);
        SpreadsheetApp.flush();

        Logger.log("正常に書き込みが完了しました！行番号: " + targetRow);

    } catch (e) {
        Logger.log("スクリプト実行エラー: " + e.toString());
        if (sheet.getLastRow() >= targetRow) {
            sheet.deleteRow(targetRow); // エラー時は挿入行を削除
        }
    }
}