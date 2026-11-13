package org.checkclassification.service;

 // SysPermissionService

import com.baomidou.mybatisplus.extension.service.IService;
import org.checkclassification.pojo.entity.SysPermission;

import java.util.List;

public interface SysPermissionService extends IService<SysPermission> {
    List<String> findPermCodesByUserId(Long userId);
}
