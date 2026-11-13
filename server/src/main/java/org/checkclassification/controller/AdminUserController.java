package org.checkclassification.controller;

 // AdminUserController

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.checkclassification.pojo.dto.IdListRequest;
import org.checkclassification.pojo.dto.UserAccountUpsertRequest;
import org.checkclassification.pojo.entity.SysUserRole;
import org.checkclassification.pojo.entity.UserAccount;
import org.checkclassification.service.SysUserRoleService;
import org.checkclassification.service.UserAccountService;
import org.checkclassification.utils.PasswordUtil;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/admin/users")
public class AdminUserController {

    @Autowired
    private UserAccountService userAccountService;

    @Autowired
    private SysUserRoleService sysUserRoleService;

    @GetMapping
    public Result<?> list(@RequestParam(required = false) String username) {

        QueryWrapper<UserAccount> wrapper = new QueryWrapper<>();
        if (StringUtils.hasText(username)) {
            wrapper.like("username", username);
        }
        wrapper.orderByDesc("id");
        List<UserAccount> users = userAccountService.list(wrapper);
        users.forEach(UserAccount::clearPassword);
        return Result.success(users);
    }

    @PostMapping
    public Result<?> create(@RequestBody UserAccountUpsertRequest request) {
        try {
            if (!StringUtils.hasText(request.getUsername()) || isEmpty(request.getPassword())) {
                return Result.error("username and password required");
            }
            QueryWrapper<UserAccount> wrapper = new QueryWrapper<>();
            wrapper.eq("username", request.getUsername());
            if (userAccountService.count(wrapper) > 0) {
                return Result.error("username already exists");
            }
            UserAccount user = new UserAccount();
            user.setUsername(request.getUsername());
            user.setPassword(PasswordUtil.sha256(request.getPassword()));
            boolean ok = userAccountService.save(user);
            user.clearPassword();
            return ok ? Result.success("创建成功") : Result.error("创建失败");
        } finally {
            request.clearPassword();
        }
    }

    @PutMapping
    public Result<?> update(@RequestBody UserAccountUpsertRequest request) {
        try {
            if (request.getId() == null) {
                return Result.error("id required");
            }
            UserAccount user = userAccountService.getById(request.getId());
            if (user == null) {
                return Result.error("user not found");
            }
            try {
                if (StringUtils.hasText(request.getUsername())) {
                    user.setUsername(request.getUsername());
                }
                if (!isEmpty(request.getPassword())) {
                    PasswordUtil.clear(user.getPassword());
                    user.setPassword(PasswordUtil.sha256(request.getPassword()));
                }
                boolean ok = userAccountService.updateById(user);
                return ok ? Result.success("更新成功") : Result.error("更新失败");
            } finally {
                user.clearPassword();
            }
        } finally {
            request.clearPassword();
        }
    }

    @DeleteMapping("/{id}")
    public Result<?> delete(@PathVariable Long id) {
        boolean ok = userAccountService.removeById(id);
        sysUserRoleService.remove(new QueryWrapper<SysUserRole>().eq("user_id", id));
        return ok ? Result.success("删除成功") : Result.error("删除失败");
    }

    @GetMapping("/{id}/roles")
    public Result<?> userRoles(@PathVariable Long id) {
        List<SysUserRole> userRoles = sysUserRoleService.list(new QueryWrapper<SysUserRole>().eq("user_id", id));
        List<Long> roleIds = userRoles.stream().map(SysUserRole::getRoleId).toList();
        Map<String, Object> data = new HashMap<>();
        data.put("roleIds", roleIds);
        data.put("roleCodes", userAccountService.getRoleCodes(id));
        return Result.success(data);
    }

    @PostMapping("/{id}/roles")
    public Result<?> bindRoles(@PathVariable Long id, @RequestBody IdListRequest request) {
        sysUserRoleService.remove(new QueryWrapper<SysUserRole>().eq("user_id", id));
        if (request.getIds() != null) {
            for (Long roleId : request.getIds()) {
                SysUserRole item = new SysUserRole();
                item.setUserId(id);
                item.setRoleId(roleId);
                sysUserRoleService.save(item);
            }
        }
        return Result.success("roles updated");
    }

    private boolean isEmpty(char[] value) {
        return value == null || value.length == 0;
    }
}
