/**
 * Main_Scriptsの2行目に最新ニュースを3件挿入する
 * 列構成: A.取得日時, B.曜日, C.AIモデル名, D.番組全台本, E.ニュースタイトル,
 *         F.愚痴内容, G.YouTube URL(空), H.ニュース取得元URL,
 *         I.取得したニュース全文, J.要約リスト, K.画像キーワードリスト, L.エール内容
 */
function generateDailyNewsScript() {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("GEMINI_API_KEY");
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Main_Scripts");

  if (!sheet) {
    Logger.log("エラー: 'Main_Scripts' という名前のシートが見つかりません。");
    return;
  }

  // 今日の日時・曜日
  const now = new Date();
  const todayStr = Utilities.formatDate(now, "JST", "yyyy/MM/dd HH:mm");
  const dayLabels = ["日", "月", "火", "水", "木", "金", "土"];
  const todayLabel = dayLabels[now.getDay()];

  Logger.log("処理開始: " + todayStr);

  const apiEndpoint =
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" +
    apiKey;

  // ==========================================
  // 3件のニュースをループで取得・挿入
  // ==========================================
  const NEWS_COUNT = 3;
  let successCount = 0;

  for (let i = 0; i < NEWS_COUNT; i++) {
    // 毎回2行目に挿入（最新が上に積み重なる）
    sheet.insertRowBefore(2);
    const targetRow = 2;
    Logger.log(`[${i + 1}/${NEWS_COUNT}] 2行目に行を挿入しました。`);

    const payload = {
      contents: [
        {
          parts: [
            {
              text:
                "優先して2026年における今月の最新のAI関連ニュースを1つ選び、以下のJSON形式のみで出力してください。余計な説明文は不要です。\n\n" +
                "【重要1】complaint（愚痴）とcheer（エール）は必ずです・ます調の敬語で記述してください。\n" +
                "【重要2】script_full（台本）は日本語で400文字以内に収めてください。動画尺を3〜5分に収めるための制約です。\n" +
                "【重要3】script_full（台本）の冒頭に「みなさんこんにちは」「はじめに」などの挨拶文を絶対に入れないでください。ニュース本文のみを記述してください。\n" +
                "【重要4】title（タイトル）は「・」「■」「●」などの記号で始めないでください。タイトル文字から始めてください。\n\n" +
                "{\n" +
                '  "ai_model": "Gemini 2.5 Flash",\n' +
                '  "title": "ニュースのタイトル",\n' +
                '  "url": "ニュースの参照URL",\n' +
                '  "script_full": "2分程度の動画用読み上げ台本",\n' +
                '  "summary_sentence": "要約1文",\n' +
                '  "image_keyword": "英語の画像検索キーワード(1〜3単語)",\n' +
                '  "complaint": "AIが人間に対して感じる愚痴。必ずです・ます調の敬語で記述すること。",\n' +
                '  "cheer": "学校や仕事などで忙しい1日を乗り越えられるような、嘘のない希望を与える一言。必ずです・ます調の敬語で記述すること。"\n' +
                "}",
            },
          ],
        },
      ],
    };

    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    };

    try {
      Logger.log(`[${i + 1}/${NEWS_COUNT}] APIリクエスト送信中...`);
      const response = UrlFetchApp.fetch(apiEndpoint, options);
      const responseCode = response.getResponseCode();
      const responseText = response.getContentText();

      if (responseCode !== 200) {
        Logger.log(
          `[${i + 1}/${NEWS_COUNT}] APIエラー (Code: ${responseCode}): ${responseText}`,
        );
        sheet.deleteRow(targetRow);
        continue;
      }

      const result = JSON.parse(responseText);
      let rawText = result.candidates[0].content.parts[0].text;

      // JSON部分のみを抽出
      const jsonMatch = rawText.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        Logger.log(
          `[${i + 1}/${NEWS_COUNT}] JSON抽出失敗。生の回答: ${rawText}`,
        );
        sheet.deleteRow(targetRow);
        continue;
      }

      const newsData = JSON.parse(jsonMatch[0]);
      Logger.log(`[${i + 1}/${NEWS_COUNT}] データ取得成功: ${newsData.title}`);

      // ==========================================
      // スプレッドシートへの書き込み
      // A.取得日時, B.曜日, C.AIモデル名, D.番組全台本, E.ニュースタイトル,
      // F.愚痴内容, G.YouTube URL(空), H.ニュース取得元URL,
      // I.取得したニュース全文, J.要約リスト, K.画像キーワードリスト, L.エール内容
      // ==========================================
      const rowValues = [
        [
          todayStr, // A: 取得日時
          todayLabel, // B: 曜日
          newsData.ai_model, // C: AIモデル名
          newsData.script_full, // D: 番組全台本
          newsData.title, // E: ニュースタイトル
          newsData.complaint, // F: 愚痴内容
          "", // G: YouTube URL（空・未処理フラグ）
          newsData.url, // H: ニュース取得元URL
          newsData.script_full, // I: 取得したニュース全文（Dと同内容）
          newsData.summary_sentence, // J: 要約リスト
          newsData.image_keyword, // K: 画像キーワードリスト
          newsData.cheer, // L: エール内容
        ],
      ];

      // ==========================================
      // 第2呼び出し: script_full の検証・修正
      // ① 冒頭挨拶の削除 ② 400文字超の場合は要約圧縮
      // ==========================================
      const verifyPayload = {
        contents: [
          {
            parts: [
              {
                text:
                  "以下のニュース台本テキストを2つのルールに従って修正し、修正後のテキストのみを出力してください。説明文・引用符・記号は不要です。\n\n" +
                  "【ルール1】冒頭に「みなさん」「こんにちは」「はじめに」「皆さん」「どうも」「ようこそ」などの挨拶・導入文があれば削除してください。\n" +
                  "【ルール2】400文字を超えている場合、ニュースの内容・文脈・重要な数字や固有名詞を維持しながら400文字以内に要約してください。\n" +
                  "【ルール3】修正後のテキストのみを出力し、説明や前置きは一切加えないでください。\n\n" +
                  "テキスト:\n" +
                  newsData.script_full,
              },
            ],
          },
        ],
      };

      const verifyOptions = {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(verifyPayload),
        muteHttpExceptions: true,
      };

      Logger.log(
        `[${i + 1}/${NEWS_COUNT}] script_full 検証・修正APIを呼び出し中...`,
      );
      Utilities.sleep(1000);

      let verifiedScript = newsData.script_full; // デフォルトは元のテキスト
      try {
        const verifyResponse = UrlFetchApp.fetch(apiEndpoint, verifyOptions);
        const verifyCode = verifyResponse.getResponseCode();
        if (verifyCode === 200) {
          const verifyResult = JSON.parse(verifyResponse.getContentText());
          const verifiedText =
            verifyResult.candidates[0].content.parts[0].text.trim();
          if (verifiedText && verifiedText.length > 0) {
            verifiedScript = verifiedText;
            Logger.log(
              `[${i + 1}/${NEWS_COUNT}] 検証完了。修正後文字数: ${verifiedScript.length}文字`,
            );
          } else {
            Logger.log(
              `[${i + 1}/${NEWS_COUNT}] 検証結果が空のため元のテキストを使用します。`,
            );
          }
        } else {
          Logger.log(
            `[${i + 1}/${NEWS_COUNT}] 検証APIエラー (Code: ${verifyCode})。元のテキストを使用します。`,
          );
        }
      } catch (verifyErr) {
        Logger.log(
          `[${i + 1}/${NEWS_COUNT}] 検証API例外: ${verifyErr.toString()}。元のテキストを使用します。`,
        );
      }

      // 検証済みscript_fullで上書き
      rowValues[0][3] = verifiedScript; // D列: 番組全台本
      rowValues[0][8] = verifiedScript; // I列: 取得したニュース全文

      sheet.getRange(targetRow, 1, 1, 12).setValues(rowValues);
      SpreadsheetApp.flush();

      Logger.log(
        `[${i + 1}/${NEWS_COUNT}] 正常に書き込み完了。行番号: ${targetRow}`,
      );
      successCount++;

      // APIレート制限への配慮（次のニュースへの待機）
      if (i < NEWS_COUNT - 1) {
        Utilities.sleep(1000);
      }
    } catch (e) {
      Logger.log(
        `[${i + 1}/${NEWS_COUNT}] スクリプト実行エラー: ${e.toString()}`,
      );
      if (sheet.getLastRow() >= targetRow) {
        sheet.deleteRow(targetRow);
      }
    }
  }

  Logger.log(
    `処理完了: ${successCount}/${NEWS_COUNT} 件のニュースを書き込みました。`,
  );
}
