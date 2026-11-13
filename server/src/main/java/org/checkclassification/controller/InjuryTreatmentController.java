package org.checkclassification.controller;

import org.checkclassification.service.InjuryTreatmentService;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

// InjuryTreatmentController
// 伤情处置建议控制器。
// - 当前接口路径为 /api/treatment
// - 入参中必须包含 injury 字段
// - 返回结果统一使用 Result 包装，便于前端统一处理

@RestController
@RequestMapping("/api/treatment")
@CrossOrigin(origins = "*") // 允许跨域访问
public class InjuryTreatmentController {

    @Autowired
    private InjuryTreatmentService injuryTreatmentService;

    /**
     * 根据伤情名称查询处置建议。
     *
     * @param param 请求参数，例如：{"injury": "头皮裂伤"}
     * @return 统一结果对象，data 中为处置建议分组结果
     */
    @PostMapping("/treatment")
    public Result<Map<String, List<String>>> getInjuryTreatment(@RequestBody Map<String, String> param) {
        try {
            String injuryType = param.get("injury");
            if (injuryType == null || injuryType.trim().isEmpty()) {
                return Result.error("请传入伤情名称");
            }

            Map<String, List<String>> treatmentMap =
                    injuryTreatmentService.getTreatmentByInjuryType(injuryType);

            if (treatmentMap.isEmpty()) {
                return Result.success("未找到对应的伤情处置建议");
            }

            return Result.success(treatmentMap);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("获取伤情处置建议失败: " + e.getMessage());
        }
    }
}
