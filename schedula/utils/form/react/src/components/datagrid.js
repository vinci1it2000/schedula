import React, {Suspense} from "react";

import {
    DataGrid,
    GridToolbarContainer,
    GridToolbarColumnsButton,
    GridToolbarDensitySelector,
    GridToolbarExport,
    GridActionsCellItem,
    GridRowModes,
    useGridApiContext
} from '@mui/x-data-grid';
import Papa from "papaparse";
import {nanoid} from "nanoid";
//import {GridRowModes} from '@mui/x-data-grid/models/gridEditRowModel';
//import {useGridApiContext} from '@mui/x-data-grid/hooks/utils/useGridApiContext';

const AddIcon = React.lazy(() => import('@mui/icons-material/Add'));
const EditIcon = React.lazy(() => import('@mui/icons-material/Edit'));
const DeleteIcon = React.lazy(() => import('@mui/icons-material/DeleteOutlined'));
const SaveIcon = React.lazy(() => import('@mui/icons-material/Save'));
const CancelIcon = React.lazy(() => import('@mui/icons-material/Close'));
const FileUploadOutlinedIcon = React.lazy(() => import('@mui/icons-material/FileUploadOutlined'));

//const DataGrid = React.lazy(() => import('@mui/x-data-grid/DataGrid/DataGrid'));
//const GridToolbarContainer = React.lazy(() => import('@mui/x-data-grid/components/containers/GridToolbarContainer'));
//const GridToolbarColumnsButton = React.lazy(() => import('@mui/x-data-grid/components/toolbar/GridToolbarColumnsButton'));
//const GridToolbarDensitySelector = React.lazy(() => import('@mui/x-data-grid/components/toolbar/GridToolbarDensitySelector'));
//const GridToolbarExport = React.lazy(() => import('@mui/x-data-grid/components/toolbar/GridToolbarExport'));
//const GridActionsCellItem = React.lazy(() => import('@mui/x-data-grid/components/cell/GridActionsCellItem'));


const Typography = React.lazy(() => import('@mui/material/Typography'));
const Stack = React.lazy(() => import('@mui/material/Stack'));
const Button = React.lazy(() => import('@mui/material/Button'));


function keyedToPlainFormData(keyedFormData) {
    if (Array.isArray(keyedFormData)) {
        return keyedFormData.map((keyedItem) => keyedItem.item);
    }
    return [];
}

function toNumeric(value) {
    if (typeof value !== "string") return value
    let number = Number(value)
    return isNaN(number) ? value : number
}

function GridToolbar({context, columns, setRowModesModel, setNewKey}) {
    let upload = (event) => {
        event.preventDefault();
        if (event.target.files.length) {
            const reader = new FileReader()
            reader.onload = async ({target}) => {
                const csv = Papa.parse(target.result, {header: false});
                let parsedData = csv?.data, header,
                    columnsFields = columns.map(v => v.field),
                    columnsHeaderNames = columns.map(v => v.headerName);
                if (parsedData[0].every(v => columnsFields.includes(v))) {
                    header = parsedData[0]
                    parsedData = parsedData.slice(1)
                } else if (parsedData[0].every(v => columnsHeaderNames.includes(v))) {
                    header = parsedData[0].map(v => (columns.find(e => (e.headerName === v)).field))
                    parsedData = parsedData.slice(1)
                } else {
                    header = columns.map(v => (v.field))
                }
                context.props.onChange(parsedData.map(r => (r.reduce((res, v, i) => {
                    res[header[i]] = toNumeric(v)
                    return res
                }, {}))))
            }
            reader.readAsText(event.target.files[0]);
            event.target.value = null;
        }
    }, title = context.props.schema.title, onAddClick = (event) => {

        if (event) {
            event.preventDefault();
        }

        const newKeyedFormDataRow = {
            key: nanoid(),
            item: context._getNewFormDataRow(),
        };
        setNewKey(newKeyedFormDataRow.key)
        const newKeyedFormData = [...context.state.keyedFormData, newKeyedFormDataRow];
        context.setState(
            {
                keyedFormData: newKeyedFormData,
                updatedKeyedFormData: true,
            },
            () => context.props.onChange(keyedToPlainFormData(newKeyedFormData))
        );

        setRowModesModel((oldModel) => ({
            ...oldModel,
            [newKeyedFormDataRow.key]: {
                mode: GridRowModes.Edit,
                fieldToFocus: columns[0].field
            },
        }));
    };

    return (<Suspense>
        <Stack spacing={1}>
            <Typography variant="button" display="block" key='title'>
                {title}
            </Typography>
            <GridToolbarContainer key='toolbar'>
                <GridToolbarColumnsButton key={1}/>
                <GridToolbarDensitySelector key={2}/>
                <GridToolbarExport key={3}/>
                {context.props.readonly ? "" :
                    <div key={4}>
                        <Button component={'label'} color="primary"
                                startIcon={<FileUploadOutlinedIcon/>}>
                            Import
                            <input accept={['csv']} type={'file'} hidden
                                   onChange={upload}></input>
                        </Button>
                    </div>}
                {!context.props.readonly && context.canAddItem(context.props.formData || []) ?
                    <Button color="primary" startIcon={<AddIcon/>}
                            onClick={onAddClick} key={5}>
                        Add record
                    </Button> : ""}
                {!context.props.readonly ?
                    <Button color="primary" startIcon={<DeleteIcon/>}
                            onClick={() => {
                                context.props.onChange([])
                            }} key={6}>
                        Delete all
                    </Button> : ""}
            </GridToolbarContainer>
        </Stack>
    </Suspense>);
}

function EditComponent(props) {
    const {id, value, field, context} = props;
    const apiRef = useGridApiContext(),
        {registry, schema} = context.props,
        {SchemaField} = registry.fields,
        schemaItems = (schema.items || {}).properties || {};
    const handleValueChange = (newValue) => {
        apiRef.current.setEditCellValue({id, field, value: newValue});
    };

    return <div style={{width: '100%'}}><SchemaField
        formData={value} schema={schemaItems[field] || {}}
        onChange={handleValueChange} registry={registry}
        idSchema={{"$id": context.props.idSchema['$id'] + '-editing'}}/>
    </div>
}

export default function _datagrid(props) {
    let {context, children, columns, ...kw} = props;
    const [rowModesModel, setRowModesModel] = React.useState({});
    const [newKey, setNewKey] = React.useState(null);
    const [pageSize, setPageSize] = React.useState(kw.pageSize || 10);
    const rows = (context.state.keyedFormData || []).map(
        ({key, item}) => (Object.assign({}, item, {id: key}))
    );
    const handleRowEditStart = (params, event) => {
        event.defaultMuiPrevented = true;
    };

    const handleRowEditStop = (params, event) => {
        event.defaultMuiPrevented = true;
    };

    const handleEditClick = (id) => () => {
        setRowModesModel({...rowModesModel, [id]: {mode: GridRowModes.Edit}});
    };

    const handleSaveClick = (id) => () => {
        setNewKey(null)
        setRowModesModel({...rowModesModel, [id]: {mode: GridRowModes.View}});
    };

    const handleDeleteClick = (id) => () => {
        let index = context.state.keyedFormData.findIndex(({key}) => key === id)
        context.onDropIndexClick(index)()
    };

    const handleCancelClick = (id) => () => {
        setRowModesModel({
            ...rowModesModel,
            [id]: {mode: GridRowModes.View, ignoreModifications: true},
        });

        if (newKey === id) {
            let index = context.state.keyedFormData.findIndex(({key}) => key === id)
            context.onDropIndexClick(index)()
        }
    };

    const processRowUpdate = (newRow) => {
        const updatedRow = {...newRow, isNew: false};
        let index = context.state.keyedFormData.findIndex(({key}) => key === newRow.id),
            data = Object.assign({}, newRow);
        delete data.id
        context.onChangeForIndex(index)(data)
        return updatedRow;
    };
    const items_properties = ((context.props.schema || {}).items || {}).properties || {};
    if (!columns) {
        const fields = new Set()
        Object.keys(items_properties).forEach(k => {
            fields.add(k)
        })
        rows.forEach(r => {
            Object.keys(r).forEach(k => {
                fields.add(k)
            })
        })
        fields.delete('id')
        columns = Array.from(fields).sort().map(k => ({field: k}))
    } else {
        columns = [...columns]
    }
    columns.forEach(d => {
        d.renderEditCell = (params) => {
            return EditComponent({context, ...params})
        }
        if (!d.hasOwnProperty('headerName')) {
            let schema = items_properties[d.field] || {}
            d.headerName = schema.hasOwnProperty('title') ? schema.title : d.field
        }
        if (!d.hasOwnProperty('description')) {
            let schema = items_properties[d.field] || {}
            if (schema.hasOwnProperty('description'))
                d.description = schema.description
        }

        if (!d.hasOwnProperty('flex') && !d.hasOwnProperty('width')) {
            d.flex = 1
        }

        if (!d.hasOwnProperty('editable')) {
            d.editable = !context.props.readonly
        }
        if (!d.hasOwnProperty('valueGetter') && d.type === 'date') {
            d.valueGetter = ({value}) => value && new Date(value)
        }
    })
    if (!context.props.readonly) {
        columns.push({
            field: 'actions',
            type: 'actions',
            width: 100,
            getActions: ({id}) => {
                const isInEditMode = rowModesModel[id]?.mode === GridRowModes.Edit;

                if (isInEditMode) {
                    return [
                        <GridActionsCellItem
                            key={'save'}
                            icon={<SaveIcon/>}
                            label="Save"
                            onClick={handleSaveClick(id)}
                        />,
                        <GridActionsCellItem
                            key={'cancel'}
                            icon={<CancelIcon/>}
                            label="Cancel"
                            className="textPrimary"
                            onClick={handleCancelClick(id)}
                            color="inherit"
                        />,
                    ];
                }

                return [
                    <GridActionsCellItem
                        key={'edit'}
                        icon={<EditIcon/>}
                        label="Edit"
                        className="textPrimary"
                        onClick={handleEditClick(id)}
                        color="inherit"
                    />,
                    <GridActionsCellItem
                        key={'delete'}
                        icon={<DeleteIcon/>}
                        label="Delete"
                        onClick={handleDeleteClick(id)}
                        color="inherit"
                    />,
                ];
            }
        })
    }

    kw.isCellEditable = () => (!context.props.readonly)

    return <Suspense><DataGrid
        autoHeight rows={rows} columns={columns}
        pageSize={pageSize}
        disableSelectionOnClick
        onPageSizeChange={(newPageSize) => setPageSize(newPageSize)}
        rowsPerPageOptions={[10, 20, 50, 100]}
        editMode="row"
        rowModesModel={rowModesModel}
        onRowModesModelChange={(newModel) => setRowModesModel(newModel)}
        onRowEditStart={handleRowEditStart}
        onRowEditStop={handleRowEditStop}
        processRowUpdate={processRowUpdate}
        components={{
            Toolbar: GridToolbar,
        }}
        componentsProps={{
            toolbar: {setRowModesModel, context, columns, setNewKey},
        }}
        experimentalFeatures={{newEditingApi: true}}
        pagination {...kw}/></Suspense>
}