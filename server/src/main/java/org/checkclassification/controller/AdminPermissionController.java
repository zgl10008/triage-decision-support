package org.checkclassification.controller;

 // AdminPermissionController

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.checkclassification.pojo.entity.SysPermission;
import org.checkclassification.service.SysPermissionService;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/admin/permissions")
public class AdminPermissionController {

    @Autowired
    private SysPermissionService permissionService;

    @GetMapping
    public Result<?> list(@RequestParam(required = false) String permName) {
        QueryWrapper<SysPermission> wrapper = new QueryWrapper<>();
        if (StringUtils.hasText(permName)) {
            wrapper.like("perm_name", permName);

        }
        wrapper.orderByDesc("id");
        return Result.success(permissionService.list(wrapper));
    }

    @PostMapping
    public Result<?> create(@RequestBody SysPermission permission) {
        if (!StringUtils.hasText(permission.getPermName()) || !StringUtils.hasText(permission.getPermCode())) {
            return Result.error("permName and permCode required");
        }
        boolean ok = permissionService.save(permission);
        return ok ? Result.success("created") : Result.error("create failed");
    }

    @PutMapping
    public Result<?> update(@RequestBody SysPermission permission) {
        if (permission.getId() == null) {
            return Result.error("id required");
        }
        boolean ok = permissionService.updateById(permission);
        return ok ? Result.success("updated") : Result.error("update failed");
    }

    @DeleteMapping("/{id}")
    public Result<?> delete(@PathVariable Long id) {
        boolean ok = permissionService.removeById(id);
        return ok ? Result.success("deleted") : Result.error("delete failed");
    }
}
