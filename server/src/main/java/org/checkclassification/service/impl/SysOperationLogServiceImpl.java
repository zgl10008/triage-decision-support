package org.checkclassification.service.impl;

 // SysOperationLogServiceImpl

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.checkclassification.mapper.SysOperationLogMapper;
import org.checkclassification.pojo.entity.SysOperationLog;
import org.checkclassification.service.SysOperationLogService;
import org.springframework.stereotype.Service;

@Service
public class SysOperationLogServiceImpl extends ServiceImpl<SysOperationLogMapper, SysOperationLog> implements SysOperationLogService {
}
