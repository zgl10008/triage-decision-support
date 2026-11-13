package org.checkclassification.service;

 // UserAccountService

import com.baomidou.mybatisplus.extension.service.IService;
import org.checkclassification.pojo.entity.UserAccount;

import java.util.List;

public interface UserAccountService extends IService<UserAccount> {
    String login(String username, char[] password);

    void logout(String token);

    UserAccount getUserByToken(String token);

    List<String> getRoleCodes(Long userId);

    boolean hasRole(Long userId, String roleCode);
}
