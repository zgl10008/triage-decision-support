package org.checkclassification.service.impl;

 // UserAccountServiceImpl

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.checkclassification.mapper.UserAccountMapper;
import org.checkclassification.pojo.entity.UserAccount;
import org.checkclassification.service.SysRoleService;
import org.checkclassification.service.UserAccountService;
import org.checkclassification.utils.PasswordUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class UserAccountServiceImpl extends ServiceImpl<UserAccountMapper, UserAccount> implements UserAccountService {

    private static final long TOKEN_TTL_SECONDS = 12 * 60 * 60;

    private final Map<String, TokenSession> tokenStore = new ConcurrentHashMap<>();

    @Autowired
    private SysRoleService sysRoleService;

    @Override
    public String login(String username, char[] password) {

        if (!StringUtils.hasText(username) || password == null || password.length == 0) {
            return null;
        }

        QueryWrapper<UserAccount> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("username", username);
        UserAccount user = baseMapper.selectOne(queryWrapper);
        if (user == null) {
            return null;
        }

        try {
            if (!PasswordUtil.verify(password, user.getPassword())) {
                return null;
            }

            String token = UUID.randomUUID().toString().replace("-", "");
            tokenStore.put(token, new TokenSession(user.getId(), user.getUsername(), Instant.now().getEpochSecond() + TOKEN_TTL_SECONDS));
            return token;
        } finally {
            user.clearPassword();
        }
    }

    @Override
    public void logout(String token) {
        if (StringUtils.hasText(token)) {
            tokenStore.remove(token);
        }
    }

    @Override
    public UserAccount getUserByToken(String token) {
        if (!StringUtils.hasText(token)) {
            return null;
        }
        TokenSession tokenSession = tokenStore.get(token);
        if (tokenSession == null) {
            return null;
        }
        if (Instant.now().getEpochSecond() > tokenSession.expireAt) {
            tokenStore.remove(token);
            return null;
        }
        return baseMapper.selectById(tokenSession.userId);
    }

    @Override
    public List<String> getRoleCodes(Long userId) {
        if (userId == null) {
            return Collections.emptyList();
        }
        return sysRoleService.findRoleCodesByUserId(userId);
    }

    @Override
    public boolean hasRole(Long userId, String roleCode) {
        if (!StringUtils.hasText(roleCode)) {
            return false;
        }
        return getRoleCodes(userId).stream().anyMatch(code -> roleCode.equalsIgnoreCase(code));
    }

    private static class TokenSession {
        private final Long userId;
        private final String username;
        private final long expireAt;

        private TokenSession(Long userId, String username, long expireAt) {
            this.userId = userId;
            this.username = username;
            this.expireAt = expireAt;
        }
    }
}
