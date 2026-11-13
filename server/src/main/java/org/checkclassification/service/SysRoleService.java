package org.checkclassification.service;

 // SysRoleService

import com.baomidou.mybatisplus.extension.service.IService;
import org.checkclassification.pojo.entity.SysRole;

import java.util.List;

public interface SysRoleService extends IService<SysRole> {
    List<String> findRoleCodesByUserId(Long userId);
}
