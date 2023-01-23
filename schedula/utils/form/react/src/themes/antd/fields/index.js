import {generateFields as coreGenerateFields} from "../../../core/fields";
import CascaderField from './CascaderField'
import CloudDownloadField from './CloudDownloadField'
import CloudUploadField from './CloudUploadField'
import ImageField from './ImageField';
import PDFField from './PDFField';
import QRCodeField from "./QRCodeField";
import StatisticField from "./StatisticField";
import TableField from './TableField';
import TabsField from './TabsField';
import VTableField from "./VTableField";

export function generateFields() {
    return {
        ...coreGenerateFields(),
        CascaderField,
        CloudDownloadField,
        CloudUploadField,
        ImageField,
        PDFField,
        QRCodeField,
        StatisticField,
        TableField,
        TabsField,
        VTableField
    }
}

export default generateFields();