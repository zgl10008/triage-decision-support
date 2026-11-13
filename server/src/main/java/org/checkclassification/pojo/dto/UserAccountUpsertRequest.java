package org.checkclassification.pojo.dto;

 // UserAccountUpsertRequest

import lombok.Data;

import java.util.Arrays;

@Data
public class UserAccountUpsertRequest {
    private Long id;
    private String username;
    private char[] password;

    public void clearPassword() {
        if (password != null) {
            Arrays.fill(password, '\0');
            password = null;
        }
    }

}
