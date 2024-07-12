import {generateTemplates as coreGenerateTemplates} from "../../../core/templates";
import {generateTemplates as antdGenerateTemplates} from "@rjsf/antd";
import React from "react";

const BaseInputTemplate = React.lazy(() => import('./BaseInputTemplate'));
const ConfigProvider = React.lazy(() => import('./ConfigProvider'));
const Debug = React.lazy(() => import('./Debug'));
const Error = React.lazy(() => import('./Error'));
const ErrorList = React.lazy(() => import('./ErrorList'));
const FieldTemplate = React.lazy(() => import('./FieldTemplate'));
const Loader = React.lazy(() => import('./Loader'));
const ModalProvider = React.lazy(() => import('./ModalProvider'));
const NotFound = React.lazy(() => import('./NotFound'));
const Skeleton = React.lazy(() => import('./Skeleton'));
const TitleFieldTemplate = React.lazy(() => import('./TitleFieldTemplate'));

export function generateTemplates() {
    return {
        ...coreGenerateTemplates(),
        ...antdGenerateTemplates(),
        BaseInputTemplate,
        ConfigProvider,
        Debug,
        Error,
        ErrorListTemplate: ErrorList,
        FieldTemplate,
        Loader,
        ModalProvider,
        NotFound,
        Skeleton,
        TitleFieldTemplate
    }
}

export default generateTemplates();
