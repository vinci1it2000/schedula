import ArrayField from './ArrayField';
import ObjectField from './ObjectField';
import PDFField from './PDFField';
import PlotlyField from './PlotlyField';

export function generateFields() {
    return {
        ArrayField,
        ObjectField,
        PDFField,
        PlotlyField
    }
}

export default generateFields();