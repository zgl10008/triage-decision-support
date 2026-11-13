package org.checkclassification.controller;

 // AdminLogController

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.checkclassification.pojo.entity.SysOperationLog;
import org.checkclassification.service.SysOperationLogService;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/admin/logs")
public class AdminLogController {

    @Autowired
    private SysOperationLogService logService;

    @GetMapping
    public Result<?> page(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "20") Integer pageSize,
            @RequestParam(required = false) String username,

            @RequestParam(required = false) String path) {

        QueryWrapper<SysOperationLog> wrapper = new QueryWrapper<>();
        if (StringUtils.hasText(username)) {
            wrapper.like("username", username);
        }
        if (StringUtils.hasText(path)) {
            wrapper.like("request_path", path);
        }
        wrapper.orderByDesc("id");
        IPage<SysOperationLog> page = logService.page(new Page<>(pageNum, pageSize), wrapper);
        return Result.success(page);
    }
}
