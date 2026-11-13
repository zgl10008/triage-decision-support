package org.checkclassification.config;

 // FfmpegStartupCheckConfig

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Configuration
public class FfmpegStartupCheckConfig {

    @Value("${ffmpeg.command:ffmpeg}")
    private String ffmpegCommand;

    @PostConstruct
    public void validateFfmpegCommand() {
        if (ffmpegCommand == null || ffmpegCommand.isBlank() || "ffmpeg".equalsIgnoreCase(ffmpegCommand.trim())) {
            System.out.println("[FFMPEG CHECK] using PATH lookup for command: ffmpeg");
            return;
        }

        Path ffmpegPath = Paths.get(ffmpegCommand);
        if (!Files.exists(ffmpegPath)) {
            throw new IllegalStateException("FFmpeg startup check failed: configured file does not exist: " + ffmpegPath);
        }
        if (!Files.isRegularFile(ffmpegPath)) {
            throw new IllegalStateException("FFmpeg startup check failed: configured path is not a file: " + ffmpegPath);
        }
        if (!Files.isExecutable(ffmpegPath)) {
            System.out.println("[FFMPEG CHECK] warning: file exists but executable check failed, path=" + ffmpegPath);
        } else {
            System.out.println("[FFMPEG CHECK] ok: " + ffmpegPath);
        }
    }
}
