package org.checkclassification.utils;

 // PasswordUtil

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;

public class PasswordUtil {

    private static final String HASH_PREFIX = "pbkdf2$";
    private static final int ITERATIONS = 120000;
    private static final int SALT_BYTES = 16;
    private static final int HASH_BYTES = 32;
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private PasswordUtil() {
    }

    public static char[] sha256(char[] raw) {

        return hash(raw);
    }

    public static char[] hash(char[] raw) {
        if (raw == null) {
            return null;
        }
        try {
            byte[] salt = new byte[SALT_BYTES];
            SECURE_RANDOM.nextBytes(salt);
            byte[] hash = pbkdf2(raw, salt, ITERATIONS, HASH_BYTES);
            return (HASH_PREFIX
                    + ITERATIONS
                    + "$"
                    + Base64.getEncoder().encodeToString(salt)
                    + "$"
                    + Base64.getEncoder().encodeToString(hash)).toCharArray();
        } catch (Exception e) {
            throw new RuntimeException("password hash failed", e);
        }
    }

    public static boolean verify(char[] raw, char[] stored) {
        if (raw == null || stored == null) {
            return false;
        }
        try {
            String storedText = new String(stored);
            if (!storedText.startsWith(HASH_PREFIX)) {
                return false;
            }

            String[] parts = storedText.split("\\$");
            if (parts.length != 4) {
                return false;
            }

            int iterations = Integer.parseInt(parts[1]);
            byte[] salt = Base64.getDecoder().decode(parts[2]);
            byte[] expected = Base64.getDecoder().decode(parts[3]);
            byte[] actual = pbkdf2(raw, salt, iterations, expected.length);
            return MessageDigest.isEqual(expected, actual);
        } catch (Exception e) {
            return false;
        }
    }

    public static void clear(char[] value) {
        if (value != null) {
            Arrays.fill(value, '\0');
        }
    }

    private static byte[] pbkdf2(char[] raw, byte[] salt, int iterations, int keyLengthBytes) throws Exception {
        PBEKeySpec spec = new PBEKeySpec(raw, salt, iterations, keyLengthBytes * 8);
        SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
        return factory.generateSecret(spec).getEncoded();
    }

    public static byte[] toBytes(char[] value) {
        return value == null ? new byte[0] : new String(value).getBytes(StandardCharsets.UTF_8);
    }
}
