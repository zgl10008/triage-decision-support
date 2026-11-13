package org.checkclassification.controller;

 // AdminKnowledgeController

import org.checkclassification.pojo.dto.KnowledgeRecordUpsertRequest;
import org.checkclassification.service.KnowledgeBaseService;
import org.checkclassification.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/admin/knowledge")
public class AdminKnowledgeController {

    @Autowired
    private KnowledgeBaseService knowledgeBaseService;

    @GetMapping
    public Result<?> list(
            @RequestParam(required = false) String injuryType,
            @RequestParam(required = false) String categoryType,
            @RequestParam(required = false) String detailKeyword) {

        try {
            return Result.success(knowledgeBaseService.list(injuryType, categoryType, detailKeyword));
        } catch (Exception e) {
            return Result.error("list failed: " + e.getMessage());
        }
    }

    @PostMapping
    public Result<?> create(@RequestBody KnowledgeRecordUpsertRequest request) {
        try {
            knowledgeBaseService.create(request);
            return Result.success("created");
        } catch (Exception e) {
            return Result.error("create failed: " + e.getMessage());
        }
    }

    @PutMapping("/{rowNo}")
    public Result<?> update(@PathVariable Integer rowNo, @RequestBody KnowledgeRecordUpsertRequest request) {
        try {
            knowledgeBaseService.update(rowNo, request);
            return Result.success("更新成功");
        } catch (Exception e) {
            return Result.error("更新失败: " + e.getMessage());
        }
    }

    @DeleteMapping("/{rowNo}")
    public Result<?> delete(@PathVariable Integer rowNo) {
        try {
            knowledgeBaseService.delete(rowNo);
            return Result.success("删除成功");
        } catch (Exception e) {
            return Result.error("删除失败: " + e.getMessage());
        }
    }
}

