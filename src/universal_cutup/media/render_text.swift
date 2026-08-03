import AppKit
import Foundation

guard CommandLine.arguments.count == 5 else {
    FileHandle.standardError.write(Data("invalid render arguments\n".utf8))
    exit(2)
}

let text = CommandLine.arguments[1]
let outputPath = CommandLine.arguments[2]
guard
    let width = Int(CommandLine.arguments[3]),
    let height = Int(CommandLine.arguments[4])
else {
    FileHandle.standardError.write(Data("invalid render dimensions\n".utf8))
    exit(2)
}

let image = NSImage(size: NSSize(width: width, height: height))
image.lockFocus()
NSColor(calibratedWhite: 0.0, alpha: 0.72).setFill()
NSRect(x: 0, y: 0, width: width, height: height).fill()

let paragraph = NSMutableParagraphStyle()
paragraph.alignment = .center
paragraph.lineBreakMode = .byWordWrapping
let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: max(18, CGFloat(height) * 0.28), weight: .semibold),
    .foregroundColor: NSColor.white,
    .paragraphStyle: paragraph,
]
let textRect = NSRect(x: 12, y: 8, width: width - 24, height: height - 16)
text.draw(in: textRect, withAttributes: attributes)
image.unlockFocus()

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let png = bitmap.representation(using: .png, properties: [:])
else {
    FileHandle.standardError.write(Data("could not encode subtitle overlay\n".utf8))
    exit(3)
}

do {
    try png.write(to: URL(fileURLWithPath: outputPath), options: .atomic)
} catch {
    FileHandle.standardError.write(Data("could not write subtitle overlay\n".utf8))
    exit(4)
}
