package org.checkclassification.pojo.dto;

 // LoginRequest

import lombok.Data;

import java.util.Arrays;

@Data
public class LoginRequest {
    private String username;
    private char[] password;

    public void clearPassword() {
        if (password != null) {
            Arrays.fill(password, '\0');
            password = null;
        }
    }
}

