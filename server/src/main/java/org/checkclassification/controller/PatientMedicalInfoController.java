package org.checkclassification.controller;

 // PatientMedicalInfoController

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.checkclassification.pojo.entity.PatientMedicalInfo;
import org.checkclassification.service.PatientMedicalInfoService;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/assessments")
public class PatientMedicalInfoController {

    @Autowired
    private PatientMedicalInfoService patientMedicalInfoService;

    @PostMapping
    public Result<?> add(@RequestBody PatientMedicalInfo patient) {
        boolean success = patientMedicalInfoService.save(patient);
        return success ? Result.success("创建成功") : Result.error("创建失败");
    }

    @PutMapping
    public Result<?> update(@RequestBody PatientMedicalInfo patient) {
        boolean success = patientMedicalInfoService.updateById(patient);
        return success ? Result.success("更新成功") : Result.error("更新失败");
    }

    @DeleteMapping("/{uid}")
    public Result<?> delete(@PathVariable String uid) {
        boolean success = patientMedicalInfoService.removeById(uid);
        return success ? Result.success("删除成功") : Result.error("删除失败");
    }

    @GetMapping("/list")
    public Result<List<PatientMedicalInfo>> getPatientList(@RequestParam(required = false) String keyword) {
        List<PatientMedicalInfo> patientList = patientMedicalInfoService.list();
        if (StringUtils.hasText(keyword)) {
            patientList = patientList.stream()
                    .filter(item -> keyword.equalsIgnoreCase(item.getUid())
                            || (item.getName() != null && item.getName().contains(keyword)))
                    .collect(Collectors.toList());
        }
        return patientList != null ? Result.success(patientList) : Result.success(List.of());
    }

    @GetMapping("/{uid}")
    public Result<PatientMedicalInfo> getById(@PathVariable String uid) {
        PatientMedicalInfo patient = patientMedicalInfoService.getById(uid);
        return patient != null ? Result.success(patient) : Result.error("patient not found");
    }

    @GetMapping("/page")
    public Result<IPage<PatientMedicalInfo>> getPage(
            @RequestParam Integer pageNum,
            @RequestParam Integer pageSize,
            @RequestParam(required = false) String keyword) {

        Page<PatientMedicalInfo> page = new Page<>(pageNum, pageSize);
        IPage<PatientMedicalInfo> resultPage = patientMedicalInfoService.findPage(page, keyword);
        return Result.success(resultPage);
    }
}
