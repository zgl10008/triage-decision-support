package org.checkclassification.controller;

 // AdminRoleController

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.checkclassification.pojo.dto.IdListRequest;
import org.checkclassification.pojo.entity.SysRole;
import org.checkclassification.pojo.entity.SysRolePermission;
import org.checkclassification.pojo.entity.SysUserRole;
import org.checkclassification.service.SysRolePermissionService;
import org.checkclassification.service.SysRoleService;
import org.checkclassification.service.SysUserRoleService;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/admin/roles")
public class AdminRoleController {

    @Autowired
    private SysRoleService sysRoleService;

    @Autowired
    private SysUserRoleService sysUserRoleService;

    @Autowired
    private SysRolePermissionService sysRolePermissionService;

    @GetMapping
    public Result<?> list(@RequestParam(required = false) String roleName) {
        QueryWrapper<SysRole> wrapper = new QueryWrapper<>();
        if (StringUtils.hasText(roleName)) {
            wrapper.like("role_name", roleName);
        }
        wrapper.orderByDesc("id");
        return Result.success(sysRoleService.list(wrapper));
    }

    @PostMapping
    public Result<?> create(@RequestBody SysRole role) {
        if (!StringUtils.hasText(role.getRoleName()) || !StringUtils.hasText(role.getRoleCode())) {
            return Result.error("roleName and roleCode required");
        }
        boolean ok = sysRoleService.save(role);
        return ok ? Result.success("创建成功") : Result.error("创建失败");
    }

    @PutMapping
    public Result<?> update(@RequestBody SysRole role) {
        if (role.getId() == null) {
            return Result.error("id required");
        }
        boolean ok = sysRoleService.updateById(role);
        return ok ? Result.success("更新成功") : Result.error("更新失败");
    }

    @DeleteMapping("/{id}")
    public Result<?> delete(@PathVariable Long id) {
        boolean ok = sysRoleService.removeById(id);
        sysUserRoleService.remove(new QueryWrapper<SysUserRole>().eq("role_id", id));
        sysRolePermissionService.remove(new QueryWrapper<SysRolePermission>().eq("role_id", id));
        return ok ? Result.success("删除成功") : Result.error("删除失败");
    }

    @GetMapping("/{id}/permissions")
    public Result<?> rolePermissions(@PathVariable Long id) {
        List<Long> permissionIds = sysRolePermissionService.list(
                new QueryWrapper<SysRolePermission>().eq("role_id", id)
        ).stream().map(SysRolePermission::getPermissionId).toList();
        return Result.success(Map.of("permissionIds", permissionIds));
    }

    @PostMapping("/{id}/permissions")
    public Result<?> bindPermissions(@PathVariable Long id, @RequestBody IdListRequest request) {
        sysRolePermissionService.remove(new QueryWrapper<SysRolePermission>().eq("role_id", id));
        if (request.getIds() != null) {
            for (Long permissionId : request.getIds()) {
                SysRolePermission item = new SysRolePermission();
                item.setRoleId(id);
                item.setPermissionId(permissionId);
                sysRolePermissionService.save(item);
            }
        }
        return Result.success("permissions updated");
    }
}
