package org.checkclassification.controller;

 // SpeechRecognitionController

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import org.checkclassification.pojo.entity.UserAccount;
import org.checkclassification.service.UserAccountService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Base64;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TimeZone;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api")
public class SpeechRecognitionController {

    private static final String HOST = "iat-api.xfyun.cn";
    private static final String PATH = "/v2/iat";
    private static final long MAX_AUDIO_FILE_SIZE = 10L * 1024 * 1024;
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(".wav", ".webm", ".ogg", ".mp4", ".m4a");
    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            "audio/wav",
            "audio/wave",
            "audio/x-wav",

            "audio/webm",
            "audio/ogg",
            "audio/mp4",
            "audio/x-m4a",
            "video/mp4"
    );

    private final ObjectMapper mapper;
    private final UserAccountService userAccountService;

    @Value("${xf.appid}")
    private String appId;

    @Value("${xf.apikey}")
    private String apiKey;

    @Value("${xf.apisecret}")
    private String apiSecret;

    @Value("${ffmpeg.command:ffmpeg}")
    private String ffmpegCommand;

    public SpeechRecognitionController(ObjectMapper mapper, UserAccountService userAccountService) {
        this.mapper = mapper;
        this.userAccountService = userAccountService;
    }

    @PostMapping("/asr")
    public Map<String, Object> recognizeSpeech(
            @RequestHeader(value = "Authorization", required = false) String authorization,
            HttpServletRequest servletRequest,
            @RequestParam("audio") MultipartFile audioFile,
            @RequestParam(value = "lang", defaultValue = "zh-CN") String lang) {

        StringBuilder textBuf = new StringBuilder();
        Map<String, Object> resp = new HashMap<>();

        try {
            UserAccount user = userAccountService.getUserByToken(extractToken(authorization));
            if (user == null && !isTrustedLocalFrontend(servletRequest)) {
                resp.put("code", 401);
                resp.put("message", "not login or token expired");
                return resp;
            }
            validateAudioFile(audioFile);
            byte[] pcm16k = toPcm16kMonoWithFFmpeg(audioFile);

            String httpsUrl = getAuthUrl();
            String wssUrl = httpsUrl.replaceFirst("^https", "wss");

            OkHttpClient client = new OkHttpClient();
            Request request = new Request.Builder().url(wssUrl).build();
            CountDownLatch doneSignal = new CountDownLatch(1);
            final int chunkSize = 1280;

            WebSocketListener listener = new WebSocketListener() {
                @Override
                public void onOpen(WebSocket webSocket, Response response) {
                    try {
                        Map<String, Object> firstFrame = new LinkedHashMap<>();
                        firstFrame.put("common", Map.of("app_id", appId));

                        Map<String, Object> business = new HashMap<>();
                        business.put("language", lang.startsWith("en") ? "en_us" : "zh_cn");
                        business.put("domain", "iat");
                        business.put("accent", "mandarin");
                        firstFrame.put("business", business);

                        Map<String, Object> data = new HashMap<>();
                        data.put("status", 0);
                        data.put("format", "audio/L16;rate=16000");
                        data.put("encoding", "raw");
                        data.put("audio", Base64.getEncoder().encodeToString(
                                Arrays.copyOfRange(pcm16k, 0, Math.min(chunkSize, pcm16k.length))
                        ));
                        firstFrame.put("data", data);

                        webSocket.send(mapper.writeValueAsString(firstFrame));

                        int offset = chunkSize;
                        while (offset + chunkSize < pcm16k.length) {
                            Map<String, Object> midFrame = Map.of(
                                    "data", Map.of(
                                            "status", 1,
                                            "audio", Base64.getEncoder().encodeToString(
                                                    Arrays.copyOfRange(pcm16k, offset, offset + chunkSize)
                                            )
                                    )
                            );
                            webSocket.send(mapper.writeValueAsString(midFrame));
                            offset += chunkSize;
                            TimeUnit.MILLISECONDS.sleep(40);
                        }

                        Map<String, Object> endFrame = Map.of(
                                "data", Map.of(
                                        "status", 2,
                                        "audio", Base64.getEncoder().encodeToString(
                                                Arrays.copyOfRange(pcm16k, offset, pcm16k.length)
                                        )
                                )
                        );
                        webSocket.send(mapper.writeValueAsString(endFrame));

                    } catch (Exception e) {
                        webSocket.cancel();
                        doneSignal.countDown();
                    }
                }

                @Override
                @SuppressWarnings("unchecked")
                public void onMessage(WebSocket webSocket, String text) {
                    try {
                        Map<String, Object> resultMap = mapper.readValue(text, Map.class);

                        Number code = (Number) resultMap.get("code");
                        if (code != null && code.intValue() != 0) {
                            resp.put("code", code);
                            resp.put("message", resultMap.get("message"));
                            doneSignal.countDown();
                            return;
                        }

                        Map<String, Object> data = (Map<String, Object>) resultMap.get("data");
                        if (data != null) {
                            Map<String, Object> result = (Map<String, Object>) data.get("result");
                            if (result != null) {
                                List<Map<String, Object>> wsList = (List<Map<String, Object>>) result.get("ws");
                                if (wsList != null) {
                                    for (Map<String, Object> ws : wsList) {
                                        List<Map<String, Object>> cwList = (List<Map<String, Object>>) ws.get("cw");
                                        if (cwList != null && !cwList.isEmpty()) {
                                            String word = (String) cwList.get(0).get("w");
                                            if (word != null) {
                                                textBuf.append(word);
                                            }
                                        }
                                    }
                                }
                            }

                            Number status = (Number) data.get("status");
                            if (status != null && status.intValue() == 2) {
                                doneSignal.countDown();
                            }
                        }
                    } catch (Exception e) {
                        resp.put("code", 500);
                        resp.put("message", "speech recognition result parse failed");
                        doneSignal.countDown();
                    }
                }

                @Override
                public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                    resp.put("code", 500);
                    resp.put("message", "WebSocket connection failed: " + t.getMessage());
                    doneSignal.countDown();
                }
            };

            client.newWebSocket(request, listener);
            doneSignal.await(15, TimeUnit.SECONDS);
            client.dispatcher().executorService().shutdown();

            if (!resp.containsKey("code")) {
                resp.put("code", 0);
                resp.put("text", textBuf.toString());
            }
            return resp;

        } catch (Exception e) {
            resp.put("code", 1);
            resp.put("message", "speech recognition failed: " + e.getMessage());
            return resp;
        }
    }

    private String getAuthUrl() throws Exception {
        SimpleDateFormat sdf = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z", Locale.US);
        sdf.setTimeZone(TimeZone.getTimeZone("GMT"));
        String date = sdf.format(new Date());

        String signatureOrigin = "host: " + HOST + "\n"
                + "date: " + date + "\n"
                + "GET " + PATH + " HTTP/1.1";

        Mac mac = Mac.getInstance("hmacsha256");
        SecretKeySpec keySpec = new SecretKeySpec(apiSecret.getBytes(StandardCharsets.UTF_8), "hmacsha256");
        mac.init(keySpec);
        byte[] signatureBytes = mac.doFinal(signatureOrigin.getBytes(StandardCharsets.UTF_8));
        String signature = Base64.getEncoder().encodeToString(signatureBytes);

        String authOrigin = String.format(
                "api_key=\"%s\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"%s\"",
                apiKey, signature);
        String authorization = Base64.getEncoder().encodeToString(authOrigin.getBytes(StandardCharsets.UTF_8));

        return String.format("https://%s%s?authorization=%s&date=%s&host=%s",
                HOST,
                PATH,
                URLEncoder.encode(authorization, StandardCharsets.UTF_8.name()),
                URLEncoder.encode(date, StandardCharsets.UTF_8.name()),
                HOST);
    }

    private byte[] toPcm16kMonoWithFFmpeg(MultipartFile audioFile) throws Exception {
        Path tempDir = Files.createDirectories(Path.of(System.getProperty("java.io.tmpdir"), "checkclassification-asr"));
        Path sourcePath = Files.createTempFile(tempDir, "asr_source_", getFileExtension(audioFile.getOriginalFilename()));
        Path targetPath = Files.createTempFile(tempDir, "asr_target_", ".pcm");

        try {
            // 使用流复制写入临时文件，避免直接调用 transferTo。
            try (InputStream inputStream = audioFile.getInputStream()) {
                Files.copy(inputStream, sourcePath, StandardCopyOption.REPLACE_EXISTING);
            }

            ProcessBuilder processBuilder = new ProcessBuilder(
                    ffmpegCommand, "-y",
                    "-i", sourcePath.toAbsolutePath().toString(),
                    "-ar", "16000",
                    "-ac", "1",
                    "-f", "s16le",
                    "-acodec", "pcm_s16le",
                    targetPath.toAbsolutePath().toString()
            );
            processBuilder.redirectErrorStream(true);
            Process process = processBuilder.start();

            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                while (reader.readLine() != null) {
                    // consume ffmpeg output
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                throw new RuntimeException("FFmpeg transcoding failed, exit code: " + exitCode);
            }

            return Files.readAllBytes(targetPath);
        } finally {
            Files.deleteIfExists(sourcePath);
            Files.deleteIfExists(targetPath);
        }
    }

    private String getFileExtension(String fileName) {
        if (fileName == null || !fileName.contains(".")) {
            return ".tmp";
        }
        return fileName.substring(fileName.lastIndexOf('.'));
    }

    private void validateAudioFile(MultipartFile audioFile) {
        if (audioFile == null || audioFile.isEmpty()) {
            throw new IllegalArgumentException("audio file must not be empty");
        }
        if (audioFile.getSize() > MAX_AUDIO_FILE_SIZE) {
            throw new IllegalArgumentException("audio file size must not exceed 10MB");
        }

        String extension = getFileExtension(audioFile.getOriginalFilename()).toLowerCase(Locale.ROOT);
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            throw new IllegalArgumentException("only wav, webm, ogg, mp4 and m4a audio formats are supported");
        }

        String contentType = Optional.ofNullable(audioFile.getContentType())
                .map(type -> type.toLowerCase(Locale.ROOT))
                .map(type -> {
                    int separatorIndex = type.indexOf(';');
                    return separatorIndex >= 0 ? type.substring(0, separatorIndex).trim() : type.trim();
                })
                .orElse("");
        if (!ALLOWED_CONTENT_TYPES.contains(contentType)) {
            throw new IllegalArgumentException("audio Content-Type is invalid");
        }
    }

    private String extractToken(String authorization) {
        if (authorization == null || authorization.isBlank()) {
            return null;
        }
        if (authorization.startsWith("Bearer ")) {
            return authorization.substring(7);
        }
        return authorization;
    }

    private boolean isTrustedLocalFrontend(HttpServletRequest request) {
        String origin = request.getHeader("Origin");
        if ("http://localhost:5174".equalsIgnoreCase(origin)) {
            return true;
        }

        String referer = request.getHeader("Referer");
        if (referer != null && referer.startsWith("http://localhost:5174/")) {
            return true;
        }

        String remoteAddr = request.getRemoteAddr();
        return "127.0.0.1".equals(remoteAddr)
                || "0:0:0:0:0:0:0:1".equals(remoteAddr)
                || "::1".equals(remoteAddr);
    }
}
