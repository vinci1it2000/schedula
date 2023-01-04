import React from "react";
import {FileUploader} from "react-drag-drop-files";

import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import ClearIcon from '@mui/icons-material/Clear';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Chip from '@mui/material/Chip';
import DeleteIcon from '@mui/icons-material/Delete';
import BorderedSection from "../components/borderedSection";
import FilePreviewer from "../components/previewer";
import FileUploadIcon from '@mui/icons-material/FileUpload';
import DownloadForOfflineOutlinedIcon
    from '@mui/icons-material/DownloadForOfflineOutlined';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import JSZip from 'jszip';

const toBase64 = file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result.replace(
        ";base64", `;name=${encodeURIComponent(file.name)};base64`
    ));
    reader.onerror = error => reject(error);
});

function dataURLtoFile(dataurl) {

    var arr = dataurl.split(','),
        mime = arr[0].match(/:(.*?);/)[1],
        filename = decodeURIComponent(arr[0].match(/;?name=(.*?);/)[1]),
        bstr = atob(arr[1]),
        n = bstr.length,
        u8arr = new Uint8Array(n);

    while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
    }

    return new File([u8arr], filename, {type: mime});
}

function FileWidget(
    {
        multiple,
        id,
        readonly,
        disabled,
        onChange,
        value,
        schema,
        autofocus = false,
        options,
    }
) {
    const handleChange = (items) => {
        if (items instanceof File) {
            items = [items]
        } else {
            items = Array.prototype.slice.call(items)
        }
        Promise.all(items.map(toBase64)).then((values) => {
                values = files.concat(values).filter((v, i, a) => a.indexOf(v) === i)
                onChange(multiple ? values : values[0])
            }
        ).catch(error => {
            alert(error.message)
        });
    };
    const files = (value ? multiple ? value : [value] : []).filter((v) => !!v);
    const realFiles = files.map(dataURLtoFile)

    return <BorderedSection
        id={id}
        label={schema.title}
    ><Stack spacing={2} sx={{width: '100%'}}>
        {readonly || disabled || (!multiple && files.length) || (schema.maxItems && files.length >= schema.maxItems) ? null :
            <FileUploader
                handleChange={handleChange}
                multiple={!!multiple}
                types={options.accept}
                children={<Chip
                    sx={{width: '100%', ...(!files.length || !multiple ? {border: 'none'} : {})}}
                    variant="outlined"
                    color="primary"
                    icon={<FileUploadIcon/>}
                    label={`Drag File${!multiple || (schema.maxItems && (schema.maxItems - files.length) === 1) ? '' : 's'} Here or Click to Browse`}
                />}
            />}
        {files.length ?
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell align="left">Name</TableCell>
                            <TableCell align="center">Size</TableCell>
                            <TableCell align="center">Type</TableCell>
                            <TableCell align="center">Preview</TableCell>
                            <TableCell align="right">
                                {files.length > 1 ? <IconButton
                                    key={'download'}
                                    onClick={() => {
                                        const zip = new JSZip();
                                        realFiles.forEach((file) => {
                                            zip.file(file.name, file);
                                        })
                                        zip.generateAsync({type: "base64"}).then(function (base64) {
                                            const a = document.createElement('a')
                                            a.download = `${schema.title || 'file'}.zip`
                                            a.href = "data:application/zip;base64," + base64;
                                            const clickEvt = new MouseEvent('click', {
                                                view: window,
                                                bubbles: true,
                                                cancelable: true,
                                            })
                                            a.dispatchEvent(clickEvt)
                                            a.remove()
                                        }).catch(error => {
                                            alert(error.message)
                                        });
                                    }}>
                                    <FileDownloadOutlinedIcon/>
                                </IconButton> : null}
                                {!(readonly || disabled) && files.length > 1 ?
                                    <IconButton key={'delete'}
                                                onClick={() => {
                                                    onChange([])
                                                }}>
                                        <DeleteIcon/>
                                    </IconButton> : null}
                            </TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {realFiles.map((file, key) => {
                            const {name, size, type} = file;
                            return (
                                <TableRow
                                    key={key}
                                    sx={{'&:last-child td, &:last-child th': {border: 0}}}
                                >
                                    <TableCell component="th" scope="row">
                                        {name}
                                    </TableCell>
                                    <TableCell
                                        align="center">{size}</TableCell>
                                    <TableCell
                                        align="center">{type}</TableCell>
                                    <TableCell align="center">
                                        <FilePreviewer
                                            file={file}
                                            sx={{
                                                maxHeight: '80px',
                                                maxWidth: '150px'
                                            }}/>
                                    </TableCell>

                                    <TableCell align="right">
                                        <IconButton key={'download'}
                                                    onClick={() => {
                                                        const a = document.createElement('a')
                                                        a.download = name
                                                        a.href = files[key]
                                                        const clickEvt = new MouseEvent('click', {
                                                            view: window,
                                                            bubbles: true,
                                                            cancelable: true,
                                                        })
                                                        a.dispatchEvent(clickEvt)
                                                        a.remove()
                                                    }}>
                                            <DownloadForOfflineOutlinedIcon/>
                                        </IconButton>
                                        {!(readonly || disabled) ? <IconButton
                                            key={'delete'}
                                            onClick={() => {
                                                if (multiple) {
                                                    let newFiles = [...files]
                                                    newFiles.splice(key, 1)
                                                    onChange(newFiles)
                                                } else {
                                                    onChange(undefined)
                                                }
                                            }}>
                                            <ClearIcon/>
                                        </IconButton> : null}
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer> :
            null
        }
    </Stack></BorderedSection>
}

export default FileWidget;