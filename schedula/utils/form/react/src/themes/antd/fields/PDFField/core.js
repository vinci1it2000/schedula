import {useState, useEffect, useMemo} from "react";
import {Button, Modal, Col, Row, Tree, Spin, Divider, Tooltip} from 'antd';
import {getUiOptions} from "@rjsf/utils";
import {renderPDF} from '../../../../core/fields/PDFField/core'
import {FilePdfOutlined, DownOutlined} from '@ant-design/icons';
import {nanoid} from "nanoid";
import isEqual from "lodash/isEqual";
import isArray from "lodash/isArray";
import {useLocaleStore} from "../../models/locale";


function tree2keys(tree) {
    if (isArray(tree))
        return tree.reduce(
            (keys, child) => [...keys, ...tree2keys(child)], []
        )
    return (tree.children || []).reduce(
        (keys, child) => [...keys, ...tree2keys(child)], [tree.key]
    )
}

export default function PDFField({idSchema, uiSchema, formData, ...props}) {

    const {getLocale} = useLocaleStore()
    const locale = getLocale('PDFField')
    const {
        fileName,
        treeData,
        checkBoxes,
        permanentSections,
        buttonProps,
        buttonLabel
    } = useMemo(() => {
        const {
            sections,
            fileName,
            treeData = Object.entries(sections).map(([key, {name}]) => ({
                title: name || key,
                key
            })),
            buttonLabel,
            buttonProps
        } = getUiOptions(uiSchema)
        const checkBoxes = tree2keys(treeData)
        const permanentSections = Object.keys(sections).filter(x => !checkBoxes.includes(x));
        return {
            fileName,
            treeData,
            checkBoxes,
            permanentSections,
            buttonProps,
            buttonLabel
        }
    }, [uiSchema])
    const [open, setOpen] = useState(false)
    const [validSections, setValidSections] = useState(null)
    const [nextSections, setNextSections] = useState(checkBoxes)
    const [url, setUrl] = useState(null)
    useEffect(() => {
        if (validSections !== null) {
            renderPDF(idSchema, uiSchema, formData, permanentSections, validSections, setUrl, props)
        }
    }, [idSchema, uiSchema, formData, permanentSections, validSections, props, props.formContext.form.state.language])
    return <div key={idSchema.$id}>
        <Tooltip title={locale.preview}><Button
            key={'button'}
            shape={"circle"}
            type="primary" icon={<FilePdfOutlined/>}
            {...buttonProps}
            onClick={() => {
                if (validSections === null)
                    setValidSections(nextSections)
                setOpen(true)

            }}>
            {buttonLabel}
        </Button></Tooltip>
        <Modal
            key={'modal'}
            footer={[
                <Button key={'download'} disabled={!url}
                        type={"primary"} onClick={() => {
                    const a = document.createElement('a')
                    a.download = fileName || 'document.pdf'
                    a.href = url
                    const clickEvt = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                    })
                    a.dispatchEvent(clickEvt)
                    a.remove()
                }
                }>{locale.downloadFile}</Button>,
                ...(treeData.length ? [<Button
                    key={'preview'}
                    disabled={isEqual((validSections || []).sort(), nextSections.sort())}
                    type={"primary"} onClick={() => {
                    setUrl(null)
                    setValidSections(nextSections)
                }}>{locale.previewFile}</Button>] : [])]}
            styles={{body: {height: 'calc(100vh - 200px)'}}}
            width={'calc(100% - 100px)'}
            title={locale.preview}
            centered
            open={open}
            onOk={() => setOpen(false)}
            onCancel={() => setOpen(false)}>
            <Row gutter={24} style={{height: '100%'}}>
                <Col key={0} span={treeData.length ? 18 : 24}
                     style={{height: '100%'}}>
                    <Spin size={"large"} spinning={!url}>
                        {!url ? null : <iframe
                            title={nanoid()}
                            className={'pdf-viewer'}
                            src={url}/>}
                    </Spin>
                </Col>
                {treeData.length ? <Col key={1} span={6} style={{
                    height: '100%',
                    overflowY: 'auto'
                }}>
                    <Divider
                        orientation="left">{locale.titleSectionSelection}</Divider>
                    <Tree
                        showLine
                        checkable
                        switcherIcon={<DownOutlined/>}
                        defaultCheckedKeys={checkBoxes}
                        defaultExpandAll={true}
                        autoExpandParent={true}
                        onCheck={(checkedKeys, {halfCheckedKeys}) => setNextSections([...checkedKeys, ...halfCheckedKeys])}
                        treeData={treeData}
                    />
                </Col> : null}
            </Row>
        </Modal>
    </div>
}