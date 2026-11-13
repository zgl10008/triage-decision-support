package org.checkclassification.service.impl;

 // SysRolePermissionServiceImpl

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.checkclassification.mapper.SysRolePermissionMapper;
import org.checkclassification.pojo.entity.SysRolePermission;
import org.checkclassification.service.SysRolePermissionService;
import org.springframework.stereotype.Service;

@Service
public class SysRolePermissionServiceImpl extends ServiceImpl<SysRolePermissionMapper, SysRolePermission> implements SysRolePermissionService {
}
