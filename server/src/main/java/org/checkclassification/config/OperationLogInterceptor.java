package org.checkclassification.config;

 // OperationLogInterceptor

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.checkclassification.pojo.entity.SysOperationLog;
import org.checkclassification.pojo.entity.UserAccount;
import org.checkclassification.service.SysOperationLogService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
public class OperationLogInterceptor implements HandlerInterceptor {

    @Autowired
    private SysOperationLogService logService;

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        String uri = request.getRequestURI();
        if (!uri.startsWith("/api/")) {
            return;
        }

        SysOperationLog log = new SysOperationLog();
        Object userObj = request.getAttribute("loginUser");
        if (userObj instanceof UserAccount user) {
            log.setUsername(user.getUsername());
        }
        log.setRequestMethod(request.getMethod());
        log.setRequestPath(uri);
        log.setClientIp(request.getRemoteAddr());
        log.setStatusCode(response.getStatus());
        log.setMessage(ex == null ? null : ex.getMessage());
        logService.save(log);
    }
}
